from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.models import PlanAdaptationEventModel


class PlanAdaptationRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_no_commit(self, model: PlanAdaptationEventModel) -> None:
        self.db.add(model)
        self.db.flush()

    def latest_for_building(
        self, building_id: int
    ) -> PlanAdaptationEventModel | None:
        return (
            self.db.execute(
                select(PlanAdaptationEventModel)
                .where(PlanAdaptationEventModel.building_id == building_id)
                .order_by(
                    PlanAdaptationEventModel.requested_at.desc(),
                    PlanAdaptationEventModel.id.desc(),
                )
                .limit(1)
            )
            .scalars()
            .first()
        )

    def list_for_building(
        self, building_id: int
    ) -> list[PlanAdaptationEventModel]:
        return list(
            self.db.execute(
                select(PlanAdaptationEventModel)
                .where(PlanAdaptationEventModel.building_id == building_id)
                .order_by(
                    PlanAdaptationEventModel.requested_at.desc(),
                    PlanAdaptationEventModel.id.desc(),
                )
            )
            .scalars()
            .all()
        )

    def count_for_building(self, building_id: int) -> int:
        return (
            self.db.query(PlanAdaptationEventModel)
            .filter(PlanAdaptationEventModel.building_id == building_id)
            .count()
        )
