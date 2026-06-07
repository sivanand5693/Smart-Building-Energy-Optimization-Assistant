"""UC10 SensorOutageRepository — sensor_outage_events CRUD."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.models import SensorOutageEventModel


class SensorOutageRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_no_commit(self, row: SensorOutageEventModel) -> None:
        self.db.add(row)
        self.db.flush()

    def list_for_building(
        self, building_id: int
    ) -> list[SensorOutageEventModel]:
        return list(
            self.db.execute(
                select(SensorOutageEventModel)
                .where(SensorOutageEventModel.building_id == building_id)
                .order_by(
                    SensorOutageEventModel.declared_at.desc(),
                    SensorOutageEventModel.id.desc(),
                )
            )
            .scalars()
            .all()
        )

    def count_for_building(self, building_id: int) -> int:
        return int(
            self.db.execute(
                select(func.count(SensorOutageEventModel.id)).where(
                    SensorOutageEventModel.building_id == building_id
                )
            ).scalar()
            or 0
        )
