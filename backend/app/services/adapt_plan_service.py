"""UC6 AdaptPlanToOccupancyChange service (control)."""
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable

from sqlalchemy.orm import Session

from app.domain.plan_adaptation import (
    AdaptDecision,
    AdaptInputsMissing,
    AdaptPlanResult,
    OccupancyChange,
)
from app.infrastructure.models import (
    BuildingModel,
    OccupancyRecordModel,
    PlanAdaptationEventModel,
)
from app.infrastructure.repositories.occupancy_repository import (
    OccupancyRepository,
)
from app.infrastructure.repositories.plan_adaptation_repository import (
    PlanAdaptationRepository,
)
from app.infrastructure.repositories.recommendation_repository import (
    SetpointRecommendationRepository,
)
from app.services.recommendation_service import RecommendationService


logger = logging.getLogger(__name__)

MATERIAL_OCCUPANCY_DELTA_FRACTION = Decimal("0.30")


class AdaptPlanService:
    def __init__(self, db: Session):
        self.db = db
        self.occupancy_repo = OccupancyRepository(db)
        self.event_repo = PlanAdaptationRepository(db)
        self.rec_repo = SetpointRecommendationRepository(db)

    def adapt(
        self,
        building_id: int,
        occupancy_changes: Iterable[OccupancyChange],
    ) -> AdaptPlanResult:
        start = time.perf_counter()
        requested_at = datetime.now(timezone.utc)

        try:
            return self._adapt_inner(
                building_id,
                list(occupancy_changes),
                start,
                requested_at,
            )
        except AdaptInputsMissing:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

    def _adapt_inner(
        self,
        building_id: int,
        changes: list[OccupancyChange],
        start: float,
        requested_at: datetime,
    ) -> AdaptPlanResult:
        # 1. Building.
        building = self.db.get(BuildingModel, building_id)
        if building is None:
            raise AdaptInputsMissing(["building"])

        # 2. Empty payload.
        if not changes:
            raise AdaptInputsMissing(["occupancy_changes"])

        # 3. Zones belong to building.
        zone_ids_in_building = {z.id for z in building.zones}
        for ch in changes:
            if ch.zone_id not in zone_ids_in_building:
                raise AdaptInputsMissing(["zone"])

        # 4. Active plan (A2).
        active_ts = self.rec_repo.active_plan_run_timestamp(building_id)
        if active_ts is None:
            raise AdaptInputsMissing(["active_plan"])

        # 5. Per-zone materiality test (read baseline BEFORE inserting the
        # new occupancy row so a repeat payload sees a zero delta — see A3
        # and S14). Then insert the new occupancy row.
        changed_zone_ids: list[int] = []
        # Use a naive `now()` since `occupancy_records.timestamp` is naive.
        new_record_ts = datetime.utcnow()
        for ch in changes:
            baseline_row = self.occupancy_repo.latest_for_zone(ch.zone_id)
            baseline = baseline_row.occupancy_count if baseline_row is not None else 0
            denom = Decimal(max(baseline, 1))
            delta = abs(Decimal(ch.new_occupancy_count) - Decimal(baseline))
            delta_fraction = delta / denom
            if delta_fraction >= MATERIAL_OCCUPANCY_DELTA_FRACTION:
                changed_zone_ids.append(ch.zone_id)
            self.occupancy_repo.add_no_commit(
                OccupancyRecordModel(
                    zone_id=ch.zone_id,
                    timestamp=new_record_ts,
                    occupancy_count=ch.new_occupancy_count,
                )
            )

        # 6. Conditional replan.
        revised: list = []
        new_run_ts = None
        if changed_zone_ids:
            inner = RecommendationService(self.db).run_within(
                building_id, db=self.db, commit=False
            )
            revised = inner.recommendations
            new_run_ts = inner.run_timestamp
            decision = "replanned"
            reason = "material occupancy delta"
            logger.info(
                "plan_adapt_replan building_id=%s changed_zones=%s new_run_ts=%s",
                building_id,
                changed_zone_ids,
                new_run_ts.isoformat() if new_run_ts else None,
            )
        else:
            decision = "no_replan"
            reason = "no material change"

        elapsed_ms = (time.perf_counter() - start) * 1000.0

        # 7. Event row.
        event = PlanAdaptationEventModel(
            building_id=building_id,
            requested_at=requested_at,
            decision=decision,
            reason=reason,
            active_plan_run_timestamp=active_ts,
            new_run_timestamp=new_run_ts,
            changed_zone_ids=list(changed_zone_ids),
            elapsed_ms=int(elapsed_ms),
        )
        self.event_repo.save_no_commit(event)

        # 8. Single commit.
        self.db.commit()

        return AdaptPlanResult(
            building_id=building_id,
            decision=decision,
            reason=reason,
            active_plan_run_timestamp=active_ts,
            new_run_timestamp=new_run_ts,
            changed_zone_ids=list(changed_zone_ids),
            requested_at=requested_at,
            elapsed_ms=elapsed_ms,
            revised_recommendations=revised,
        )

    def list_for_building(self, building_id: int) -> list[AdaptDecision]:
        rows = self.event_repo.list_for_building(building_id)
        return [
            AdaptDecision(
                id=r.id,
                building_id=r.building_id,
                decision=r.decision,
                reason=r.reason,
                active_plan_run_timestamp=r.active_plan_run_timestamp,
                new_run_timestamp=r.new_run_timestamp,
                changed_zone_ids=list(r.changed_zone_ids or []),
                requested_at=r.requested_at,
                elapsed_ms=r.elapsed_ms,
            )
            for r in rows
        ]
