from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.models import DemandForecastModel, ZoneModel


class DemandForecastRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_all(self, rows: list[DemandForecastModel]) -> None:
        self.db.add_all(rows)
        self.db.commit()

    def latest_for_zone_at_or_before(
        self, zone_id: int, ts
    ) -> DemandForecastModel | None:
        """UC8 — locate the forecast row used by a recommendation.

        UC4 calls ``latest_for_zone(zone_id)`` at the moment of recommendation
        generation, so the matching forecast row is the latest one whose
        ``timestamp <= recommendation.run_timestamp``.
        """
        return (
            self.db.execute(
                select(DemandForecastModel)
                .where(DemandForecastModel.zone_id == zone_id)
                .where(DemandForecastModel.timestamp <= ts)
                .order_by(DemandForecastModel.timestamp.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )

    def latest_for_zone(self, zone_id: int) -> DemandForecastModel | None:
        return (
            self.db.execute(
                select(DemandForecastModel)
                .where(DemandForecastModel.zone_id == zone_id)
                .order_by(DemandForecastModel.timestamp.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )

    def latest_for_building(self, building_id: int) -> list[DemandForecastModel]:
        zone_ids = [
            z.id
            for z in self.db.query(ZoneModel)
            .filter(ZoneModel.building_id == building_id)
            .all()
        ]
        if not zone_ids:
            return []
        latest_per_zone: list[DemandForecastModel] = []
        for zid in zone_ids:
            row = (
                self.db.execute(
                    select(DemandForecastModel)
                    .where(DemandForecastModel.zone_id == zid)
                    .order_by(DemandForecastModel.timestamp.desc())
                    .limit(1)
                )
                .scalars()
                .first()
            )
            if row is not None:
                latest_per_zone.append(row)
        return latest_per_zone

    def count_for_building(self, building_id: int) -> int:
        zone_ids = [
            z.id
            for z in self.db.query(ZoneModel)
            .filter(ZoneModel.building_id == building_id)
            .all()
        ]
        if not zone_ids:
            return 0
        return (
            self.db.query(DemandForecastModel)
            .filter(DemandForecastModel.zone_id.in_(zone_ids))
            .count()
        )
