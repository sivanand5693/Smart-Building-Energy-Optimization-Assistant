from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.models import (
    AppliedSetpointChangeModel,
    DeviceModel,
)


class AppliedChangeRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_all(self, rows: list[AppliedSetpointChangeModel]) -> None:
        if not rows:
            self.db.commit()
            return
        self.db.add_all(rows)
        self.db.commit()

    def latest_for_building(
        self, building_id: int
    ) -> list[AppliedSetpointChangeModel]:
        return list(
            self.db.execute(
                select(AppliedSetpointChangeModel)
                .where(AppliedSetpointChangeModel.building_id == building_id)
                .order_by(
                    AppliedSetpointChangeModel.applied_at.asc(),
                    AppliedSetpointChangeModel.id.asc(),
                )
            )
            .scalars()
            .all()
        )

    def exists_for_recommendation(self, recommendation_id: int) -> bool:
        row = self.db.execute(
            select(AppliedSetpointChangeModel.id).where(
                AppliedSetpointChangeModel.recommendation_id
                == recommendation_id
            )
        ).first()
        return row is not None

    def count_for_building(self, building_id: int) -> int:
        return (
            self.db.query(AppliedSetpointChangeModel)
            .filter(AppliedSetpointChangeModel.building_id == building_id)
            .count()
        )


class DeviceRepository:
    def __init__(self, db: Session):
        self.db = db

    def first_hvac_for_zone(self, zone_id: int) -> DeviceModel | None:
        from sqlalchemy import func

        return (
            self.db.execute(
                select(DeviceModel)
                .where(DeviceModel.zone_id == zone_id)
                .where(func.lower(DeviceModel.device_type) == "hvac")
                .order_by(DeviceModel.id.asc())
                .limit(1)
            )
            .scalars()
            .first()
        )

    def delete_hvac_for_zone(self, zone_id: int) -> int:
        from sqlalchemy import func, delete

        result = self.db.execute(
            delete(DeviceModel)
            .where(DeviceModel.zone_id == zone_id)
            .where(func.lower(DeviceModel.device_type) == "hvac")
        )
        self.db.commit()
        return result.rowcount or 0
