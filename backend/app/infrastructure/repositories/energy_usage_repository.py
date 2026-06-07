"""UC9 EnergyUsageRepository — read+ingest helpers for `energy_usage_records`."""
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.infrastructure.models import EnergyUsageRecordModel


class EnergyUsageRepository:
    def __init__(self, db: Session):
        self.db = db

    def ingest(
        self,
        building_id: int,
        zone_id: int,
        usage_date: date,
        kind: str,
        kwh: Decimal,
    ) -> None:
        """Upsert one row by (building_id, zone_id, usage_date, kind)."""
        stmt = (
            pg_insert(EnergyUsageRecordModel)
            .values(
                building_id=building_id,
                zone_id=zone_id,
                usage_date=usage_date,
                kind=kind,
                kwh=kwh,
            )
            .on_conflict_do_update(
                index_elements=[
                    "building_id",
                    "zone_id",
                    "usage_date",
                    "kind",
                ],
                set_={"kwh": kwh},
            )
        )
        self.db.execute(stmt)
        self.db.commit()

    def for_building_date(
        self, building_id: int, usage_date: date
    ) -> list[EnergyUsageRecordModel]:
        return list(
            self.db.execute(
                select(EnergyUsageRecordModel).where(
                    EnergyUsageRecordModel.building_id == building_id,
                    EnergyUsageRecordModel.usage_date == usage_date,
                )
            )
            .scalars()
            .all()
        )
