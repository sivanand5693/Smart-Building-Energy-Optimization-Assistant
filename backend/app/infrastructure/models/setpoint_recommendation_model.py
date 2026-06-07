from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class SetpointRecommendationModel(Base):
    __tablename__ = "setpoint_recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(
        ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False
    )
    zone_id: Mapped[int] = mapped_column(
        ForeignKey("zones.id", ondelete="CASCADE"), nullable=False
    )
    run_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    setpoint_delta_f: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    projected_savings_kwh: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), nullable=False
    )
    comfort_impact: Mapped[str] = mapped_column(String(16), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    degraded_confidence: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    __table_args__ = (
        CheckConstraint(
            "comfort_impact IN ('none','minor','moderate')",
            name="ck_setpoint_recommendations_comfort_impact",
        ),
        CheckConstraint(
            "projected_savings_kwh >= 0",
            name="ck_setpoint_recommendations_savings_nonneg",
        ),
        CheckConstraint(
            "rank >= 1",
            name="ck_setpoint_recommendations_rank_positive",
        ),
        Index(
            "ix_setpoint_recommendations_building_run",
            "building_id",
            "run_timestamp",
        ),
        Index(
            "ix_setpoint_recommendations_building_run_rank",
            "building_id",
            "run_timestamp",
            "rank",
        ),
    )
