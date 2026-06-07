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
