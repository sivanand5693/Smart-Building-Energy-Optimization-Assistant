from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.models import (
    ComfortRiskAlertModel,
    ComfortRiskRunModel,
    ZoneModel,
)


class ComfortRiskRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_run_no_commit(self, run: ComfortRiskRunModel) -> None:
        self.db.add(run)
        self.db.flush()

    def save_alerts_no_commit(self, rows: list[ComfortRiskAlertModel]) -> None:
        if not rows:
            return
        self.db.add_all(rows)
        self.db.flush()

    def latest_for_building(
        self, building_id: int
    ) -> ComfortRiskRunModel | None:
        return (
            self.db.execute(
                select(ComfortRiskRunModel)
                .where(ComfortRiskRunModel.building_id == building_id)
                .order_by(
                    ComfortRiskRunModel.run_at.desc(),
                    ComfortRiskRunModel.id.desc(),
                )
                .limit(1)
            )
            .scalars()
            .first()
        )

    def alerts_for_run(self, run_id: int) -> list[ComfortRiskAlertModel]:
        return list(
            self.db.execute(
                select(ComfortRiskAlertModel)
                .where(ComfortRiskAlertModel.run_id == run_id)
                .order_by(ComfortRiskAlertModel.zone_id.asc())
            )
            .scalars()
            .all()
        )

    def count_runs_for_building(self, building_id: int) -> int:
        return (
            self.db.query(ComfortRiskRunModel)
            .filter(ComfortRiskRunModel.building_id == building_id)
            .count()
        )

    def count_alerts_for_building(self, building_id: int) -> int:
        return (
            self.db.query(ComfortRiskAlertModel)
            .join(ZoneModel, ZoneModel.id == ComfortRiskAlertModel.zone_id)
            .filter(ZoneModel.building_id == building_id)
            .count()
        )
