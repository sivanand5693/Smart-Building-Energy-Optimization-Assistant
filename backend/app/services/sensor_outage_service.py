"""UC10 HandleSensorDataOutage service."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.sensor_outage import (
    SensorOutageForcedDbError,
    SensorOutageInputsMissing,
    SensorOutageResult,
)
from app.infrastructure.models import (
    BuildingModel,
    DemandForecastModel,
    SensorOutageEventModel,
)
from app.infrastructure.repositories.forecast_repository import (
    DemandForecastRepository,
)
from app.infrastructure.repositories.recommendation_repository import (
    SetpointRecommendationRepository,
)
from app.infrastructure.repositories.sensor_outage_repository import (
    SensorOutageRepository,
)


logger = logging.getLogger(__name__)


# -- Test lever (S11) --------------------------------------------------------

_FORCE_DB_ERROR_NEXT_REQUEST = False


def force_db_error_next_request() -> None:
    global _FORCE_DB_ERROR_NEXT_REQUEST
    _FORCE_DB_ERROR_NEXT_REQUEST = True


def _consume_force_db_error() -> bool:
    global _FORCE_DB_ERROR_NEXT_REQUEST
    flag = _FORCE_DB_ERROR_NEXT_REQUEST
    _FORCE_DB_ERROR_NEXT_REQUEST = False
    return flag


RECENT_FORECAST_WINDOW = timedelta(hours=24)


class SensorOutageService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = SensorOutageRepository(db)
        self.forecast_repo = DemandForecastRepository(db)
        self.rec_repo = SetpointRecommendationRepository(db)

    def handle(
        self,
        building_id: int,
        affected_zone_ids: list,
        reason: str,
    ) -> SensorOutageResult:
        start = time.perf_counter()
        try:
            return self._handle_inner(
                building_id, affected_zone_ids, reason, start
            )
        except SensorOutageInputsMissing:
            self.db.rollback()
            raise
        except SensorOutageForcedDbError:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

    def _handle_inner(
        self,
        building_id: int,
        affected_zone_ids: list,
        reason: str,
        start: float,
    ) -> SensorOutageResult:
        # 1. Validate inputs (collect missing labels)
        missing: set[str] = set()

        building = self.db.get(BuildingModel, building_id) if isinstance(building_id, int) else None
        if building is None:
            missing.add("building")

        normalized_zones: list[int] = []
        if isinstance(affected_zone_ids, list):
            for z in affected_zone_ids:
                if isinstance(z, int):
                    normalized_zones.append(z)
        if not normalized_zones:
            missing.add("affected_zone_ids")

        reason_str = reason if isinstance(reason, str) else ""
        if not reason_str.strip():
            missing.add("reason")

        # If the building is unknown we can't check zone membership; surface
        # only the labels we know are missing.
        if building is not None and normalized_zones:
            building_zone_ids = {z.id for z in building.zones}
            if any(zid not in building_zone_ids for zid in normalized_zones):
                missing.add("zone")

        if missing:
            raise SensorOutageInputsMissing(sorted(missing))

        # Past this point: building is non-None and zone ids are valid.
        assert building is not None  # for type checker

        # 2. Decision rule (A1)
        all_zone_ids = {z.id for z in building.zones}
        covers_all = set(normalized_zones) == all_zone_ids

        recent_cutoff = datetime.now(timezone.utc) - RECENT_FORECAST_WINDOW
        recent_count = (
            self.db.execute(
                select(DemandForecastModel.id)
                .where(DemandForecastModel.zone_id.in_(normalized_zones))
                .where(DemandForecastModel.created_at >= recent_cutoff)
                .limit(1)
            )
            .scalars()
            .first()
        )
        has_recent = recent_count is not None
        decision = "paused" if (covers_all and not has_recent) else "fallback"

        # 3. Flag updates (fallback only)
        degraded_forecast_zone_ids: list[int] = []
        degraded_rec_ids: list[int] = []
        if decision == "fallback":
            for zid in normalized_zones:
                updated_id = self.forecast_repo.mark_latest_degraded_for_zone(zid)
                if updated_id is not None:
                    degraded_forecast_zone_ids.append(zid)
            degraded_rec_ids = self.rec_repo.mark_latest_run_degraded_for_zones(
                building_id, normalized_zones
            )

        # 4. Notes (A8)
        if decision == "paused":
            notes = (
                f"{reason_str} | no recent forecast for any zone — "
                f"planning paused"
            )
        else:
            notes = reason_str

        # 5. Forced DB error lever
        if _consume_force_db_error():
            raise SensorOutageForcedDbError("forced_db_error_for_test")

        # 6. Persist event row
        elapsed_ms_int = int((time.perf_counter() - start) * 1000.0)
        declared_at = datetime.now(timezone.utc)
        event_row = SensorOutageEventModel(
            building_id=building_id,
            declared_at=declared_at,
            affected_zone_ids=list(normalized_zones),
            reason=reason_str,
            decision=decision,
            notes=notes,
            elapsed_ms=elapsed_ms_int,
        )
        self.repo.save_no_commit(event_row)
        self.db.commit()

        # 7. Log (A4)
        logger.info(
            "sensor_outage_handled building_id=%s decision=%s "
            "affected_zone_ids=%s elapsed_ms=%s",
            building_id,
            decision,
            normalized_zones,
            elapsed_ms_int,
        )

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return SensorOutageResult(
            event_id=event_row.id,
            building_id=building_id,
            affected_zone_ids=list(normalized_zones),
            decision=decision,
            notes=notes,
            degraded_forecast_zone_ids=degraded_forecast_zone_ids,
            degraded_recommendation_ids=degraded_rec_ids,
            elapsed_ms=elapsed_ms,
            declared_at=declared_at,
        )

    def list_events(self, building_id: int) -> list[SensorOutageEventModel]:
        return self.repo.list_for_building(building_id)
