from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.models import RecommendationExplanationModel


class ExplanationRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_no_commit(self, row: RecommendationExplanationModel) -> None:
        self.db.add(row)
        self.db.flush()

    def get_for_recommendation(
        self, recommendation_id: int
    ) -> RecommendationExplanationModel | None:
        return (
            self.db.execute(
                select(RecommendationExplanationModel).where(
                    RecommendationExplanationModel.recommendation_id
                    == recommendation_id
                )
            )
            .scalars()
            .first()
        )

    def count_for_recommendation(self, recommendation_id: int) -> int:
        return (
            self.db.query(RecommendationExplanationModel)
            .filter(
                RecommendationExplanationModel.recommendation_id
                == recommendation_id
            )
            .count()
        )
