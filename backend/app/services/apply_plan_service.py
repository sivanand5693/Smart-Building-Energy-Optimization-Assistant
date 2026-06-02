import time
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.applied_change import (
    AppliedChange,
    ApplyInputsMissing,
    ApplyPlanRunResult,
)
from app.infrastructure.adapters.device_control_adapter import registry
from app.infrastructure.models import (
    AppliedSetpointChangeModel,
    BuildingModel,
    SetpointRecommendationModel,
)
from app.infrastructure.repositories.applied_change_repository import (
    AppliedChangeRepository,
    DeviceRepository,
)


class ApplyPlanService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AppliedChangeRepository(db)
        self.device_repo = DeviceRepository(db)

    def apply(
        self, building_id: int, recommendation_ids: list[int]
    ) -> ApplyPlanRunResult:
        start = time.perf_counter()
        applied_at = datetime.now(timezone.utc)

        building = self.db.get(BuildingModel, building_id)
        if building is None:
            raise ApplyInputsMissing(["building"])

        # Load recommendations and validate ownership
        recs = list(
            self.db.execute(
                select(SetpointRecommendationModel).where(
                    SetpointRecommendationModel.id.in_(recommendation_ids)
                )
            )
            .scalars()
            .all()
        )
        if len(recs) != len(set(recommendation_ids)):
            raise ApplyInputsMissing(["recommendation"])
        for r in recs:
            if r.building_id != building_id:
                raise ApplyInputsMissing(["recommendation"])

        # Determine latest run_timestamp for the target building
        latest_ts = (
            self.db.execute(
                select(SetpointRecommendationModel.run_timestamp)
                .where(SetpointRecommendationModel.building_id == building_id)
                .order_by(SetpointRecommendationModel.run_timestamp.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        if latest_ts is None:
            # Building has no recs at all but caller submitted ids that we
            # already validated belong to this building -> defensive.
            raise ApplyInputsMissing(["recommendation"])
        for r in recs:
            if r.run_timestamp != latest_ts:
                raise ApplyInputsMissing(["stale_run"])

        # Sort by rank ASC
        recs.sort(key=lambda r: r.rank)

        pending: list[AppliedSetpointChangeModel] = []
        result_rows: list[AppliedChange] = []

        for r in recs:
            device = self.device_repo.first_hvac_for_zone(r.zone_id)
            if device is None:
                row = AppliedSetpointChangeModel(
                    recommendation_id=r.id,
                    building_id=r.building_id,
                    zone_id=r.zone_id,
                    applied_at=applied_at,
                    setpoint_delta_f=r.setpoint_delta_f,
                    status="failed",
                    error_code="missing_device",
                    adapter_message="no HVAC device for zone",
                    latency_ms=0,
                )
                pending.append(row)
                result_rows.append(
                    AppliedChange(
                        recommendation_id=r.id,
                        building_id=r.building_id,
                        zone_id=r.zone_id,
                        applied_at=applied_at,
                        setpoint_delta_f=Decimal(r.setpoint_delta_f),
                        status="failed",
                        error_code="missing_device",
                        adapter_message="no HVAC device for zone",
                        latency_ms=0,
                    )
                )
                continue

            if self.repo.exists_for_recommendation(r.id):
                row = AppliedSetpointChangeModel(
                    recommendation_id=r.id,
                    building_id=r.building_id,
                    zone_id=r.zone_id,
                    applied_at=applied_at,
                    setpoint_delta_f=r.setpoint_delta_f,
                    status="failed",
                    error_code="already_applied",
                    adapter_message="recommendation already applied",
                    latency_ms=0,
                )
                # NOTE: DB has a UNIQUE on recommendation_id, so we MUST NOT
                # try to insert another applied row for this rec. We surface
                # the short-circuit only in the API result, not in the DB.
                result_rows.append(
                    AppliedChange(
                        recommendation_id=r.id,
                        building_id=r.building_id,
                        zone_id=r.zone_id,
                        applied_at=applied_at,
                        setpoint_delta_f=Decimal(r.setpoint_delta_f),
                        status="failed",
                        error_code="already_applied",
                        adapter_message="recommendation already applied",
                        latency_ms=0,
                    )
                )
                continue

            outcome = registry.device_control.dispatch(
                device.id,
                r.zone_id,
                Decimal(r.setpoint_delta_f),
                r.run_timestamp,
                r.id,
            )

            row = AppliedSetpointChangeModel(
                recommendation_id=r.id,
                building_id=r.building_id,
                zone_id=r.zone_id,
                applied_at=applied_at,
                setpoint_delta_f=r.setpoint_delta_f,
                status=outcome.status,
                error_code=outcome.error_code,
                adapter_message=outcome.adapter_message,
                latency_ms=outcome.latency_ms,
            )
            pending.append(row)
            result_rows.append(
                AppliedChange(
                    recommendation_id=r.id,
                    building_id=r.building_id,
                    zone_id=r.zone_id,
                    applied_at=applied_at,
                    setpoint_delta_f=Decimal(r.setpoint_delta_f),
                    status=outcome.status,
                    error_code=outcome.error_code,
                    adapter_message=outcome.adapter_message,
                    latency_ms=outcome.latency_ms,
                )
            )

        self.repo.save_all(pending)

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return ApplyPlanRunResult(
            building_id=building_id,
            applied_at=applied_at,
            elapsed_ms=elapsed_ms,
            results=result_rows,
        )

    def latest_for_building(self, building_id: int) -> list[AppliedChange]:
        rows = self.repo.latest_for_building(building_id)
        return [
            AppliedChange(
                recommendation_id=r.recommendation_id,
                building_id=r.building_id,
                zone_id=r.zone_id,
                applied_at=r.applied_at,
                setpoint_delta_f=Decimal(r.setpoint_delta_f),
                status=r.status,
                error_code=r.error_code,
                adapter_message=r.adapter_message,
                latency_ms=r.latency_ms,
            )
            for r in rows
        ]
