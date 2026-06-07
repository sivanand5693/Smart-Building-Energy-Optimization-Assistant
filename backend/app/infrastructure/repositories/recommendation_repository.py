from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.models import (
    AppliedSetpointChangeModel,
    SetpointRecommendationModel,
    ZoneComfortConstraintModel,
)


class SetpointRecommendationRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_all(self, rows: list[SetpointRecommendationModel]) -> None:
        self.db.add_all(rows)
        self.db.commit()

    def save_all_no_commit(self, rows: list[SetpointRecommendationModel]) -> None:
        if not rows:
            return
        self.db.add_all(rows)
        self.db.flush()

    def active_plan_run_timestamp(self, building_id: int) -> datetime | None:
        """Return the latest setpoint_recommendations.run_timestamp for the
        building whose ids intersect >=1 applied_setpoint_changes row
        (UC6 active-plan definition; A2).
        """
        return (
            self.db.execute(
                select(SetpointRecommendationModel.run_timestamp)
                .join(
                    AppliedSetpointChangeModel,
                    AppliedSetpointChangeModel.recommendation_id
                    == SetpointRecommendationModel.id,
                )
                .where(SetpointRecommendationModel.building_id == building_id)
                .order_by(SetpointRecommendationModel.run_timestamp.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )

    def latest_run_timestamp_for_building(
        self, building_id: int
    ) -> datetime | None:
        """Return the latest setpoint_recommendations.run_timestamp for the
        building, regardless of applied state (UC7 A3 — "active or proposed").
        """
        return (
            self.db.execute(
                select(SetpointRecommendationModel.run_timestamp)
                .where(SetpointRecommendationModel.building_id == building_id)
                .order_by(SetpointRecommendationModel.run_timestamp.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )

    def latest_rows_for_building(
        self, building_id: int, run_timestamp: datetime
    ) -> list[SetpointRecommendationModel]:
        """All setpoint_recommendations rows for the building at the given
        run_timestamp. Used by UC7 to look up `setpoint_delta_f` per zone."""
        return list(
            self.db.execute(
                select(SetpointRecommendationModel)
                .where(SetpointRecommendationModel.building_id == building_id)
                .where(SetpointRecommendationModel.run_timestamp == run_timestamp)
                .order_by(SetpointRecommendationModel.zone_id.asc())
            )
            .scalars()
            .all()
        )

    def latest_for_building(
        self, building_id: int
    ) -> list[SetpointRecommendationModel]:
        # Find most recent run_timestamp for the building, then return all rows
        # with that timestamp ordered by rank ASC.
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
            return []
        return list(
            self.db.execute(
                select(SetpointRecommendationModel)
                .where(SetpointRecommendationModel.building_id == building_id)
                .where(SetpointRecommendationModel.run_timestamp == latest_ts)
                .order_by(SetpointRecommendationModel.rank.asc())
            )
            .scalars()
            .all()
        )

    def count_for_building(self, building_id: int) -> int:
        return (
            self.db.query(SetpointRecommendationModel)
            .filter(SetpointRecommendationModel.building_id == building_id)
            .count()
        )

    def mark_latest_run_degraded_for_zones(
        self, building_id: int, zone_ids: list[int]
    ) -> list[int]:
        """UC10 — set degraded_confidence=true on every setpoint_recommendations
        row whose (building_id, run_timestamp) matches the latest run for the
        building AND whose zone_id is in zone_ids. Returns the updated row ids.
        No commit — caller owns the transaction."""
        if not zone_ids:
            return []
        latest_ts = (
            self.db.execute(
                select(SetpointRecommendationModel.run_timestamp)
                .where(SetpointRecommendationModel.building_id == building_id)
                .where(SetpointRecommendationModel.zone_id.in_(zone_ids))
                .order_by(SetpointRecommendationModel.run_timestamp.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        if latest_ts is None:
            return []
        rows = list(
            self.db.execute(
                select(SetpointRecommendationModel)
                .where(SetpointRecommendationModel.building_id == building_id)
                .where(SetpointRecommendationModel.run_timestamp == latest_ts)
                .where(SetpointRecommendationModel.zone_id.in_(zone_ids))
            )
            .scalars()
            .all()
        )
        updated: list[int] = []
        for r in rows:
            if not r.degraded_confidence:
                r.degraded_confidence = True
                updated.append(r.id)
            else:
                updated.append(r.id)
        if rows:
            self.db.flush()
        return updated


class ZoneComfortConstraintRepository:
    def __init__(self, db: Session):
        self.db = db

    def for_zone(
        self, zone_id: int
    ) -> ZoneComfortConstraintModel | None:
        return self.db.get(ZoneComfortConstraintModel, zone_id)

    def upsert(self, row: ZoneComfortConstraintModel) -> None:
        existing = self.db.get(ZoneComfortConstraintModel, row.zone_id)
        if existing is None:
            self.db.add(row)
        else:
            existing.min_setpoint_f = row.min_setpoint_f
            existing.max_setpoint_f = row.max_setpoint_f
            existing.occupied_min_f = row.occupied_min_f
            existing.occupied_max_f = row.occupied_max_f
            existing.unoccupied_min_f = row.unoccupied_min_f
            existing.unoccupied_max_f = row.unoccupied_max_f
        self.db.commit()

    def delete(self, zone_id: int) -> None:
        existing = self.db.get(ZoneComfortConstraintModel, zone_id)
        if existing is not None:
            self.db.delete(existing)
            self.db.commit()
