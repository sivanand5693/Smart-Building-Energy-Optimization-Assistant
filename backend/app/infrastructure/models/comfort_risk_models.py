from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class ComfortRiskRunModel(Base):
    __tablename__ = "comfort_risk_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(
        ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False
    )
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(8), nullable=False)
    alerts_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_run_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "decision IN ('alert','pass')",
            name="ck_comfort_risk_runs_decision",
        ),
        Index(
            "ix_comfort_risk_runs_building_run_at",
            "building_id",
            "run_at",
        ),
    )


class ComfortRiskAlertModel(Base):
    __tablename__ = "comfort_risk_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("comfort_risk_runs.id", ondelete="CASCADE"), nullable=False
    )
    zone_id: Mapped[int] = mapped_column(
        ForeignKey("zones.id", ondelete="CASCADE"), nullable=False
    )
    projected_temp_f: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    occupied_min_f: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    occupied_max_f: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    risk_score: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    mitigation: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "direction IN ('above','below')",
            name="ck_comfort_risk_alerts_direction",
        ),
        Index("ix_comfort_risk_alerts_run", "run_id"),
    )
