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

    def latest_for_zone(self, zone_id: int) -> OccupancyRecordModel | None:
        return (
            self.db.query(OccupancyRecordModel)
            .filter(OccupancyRecordModel.zone_id == zone_id)
            .order_by(OccupancyRecordModel.timestamp.desc())
            .first()
        )

    def latest_for_zone_at_or_before(
        self, zone_id: int, ts
    ) -> OccupancyRecordModel | None:
        from datetime import datetime as _dt

        # `occupancy_records.timestamp` is stored as a naive timestamp in
        # the project schema. If the caller passes an aware datetime we
        # strip the tz so the comparison is apples-to-apples.
        cmp_ts = ts
        if isinstance(ts, _dt) and ts.tzinfo is not None:
            cmp_ts = ts.replace(tzinfo=None)
        return (
            self.db.query(OccupancyRecordModel)
            .filter(OccupancyRecordModel.zone_id == zone_id)
            .filter(OccupancyRecordModel.timestamp <= cmp_ts)
            .order_by(OccupancyRecordModel.timestamp.desc())
            .first()
        )

    def add_no_commit(self, record: OccupancyRecordModel) -> None:
        self.db.add(record)
        self.db.flush()
