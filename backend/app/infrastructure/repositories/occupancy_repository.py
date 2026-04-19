from sqlalchemy.orm import Session

from app.domain.occupancy_schedule import OccupancyRecordInput
from app.infrastructure.models import OccupancyRecordModel


class OccupancyRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_all(self, records: list[OccupancyRecordInput]) -> int:
        rows = [
            OccupancyRecordModel(
                zone_id=r.zone_id,
                timestamp=r.timestamp,
                occupancy_count=r.occupancy_count,
            )
            for r in records
        ]
        self.db.add_all(rows)
        self.db.commit()
        return len(rows)
