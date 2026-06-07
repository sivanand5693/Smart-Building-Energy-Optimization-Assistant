from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class RecommendationExplanationModel(Base):
    __tablename__ = "recommendation_explanations"

    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("setpoint_recommendations.id", ondelete="CASCADE"),
        nullable=False,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    factors_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "recommendation_id",
            name="uq_recommendation_explanations_recommendation",
        ),
        Index(
            "ix_recommendation_explanations_recommendation",
            "recommendation_id",
        ),
    )
