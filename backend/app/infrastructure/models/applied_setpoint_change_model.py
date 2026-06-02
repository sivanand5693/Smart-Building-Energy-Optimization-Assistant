from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class AppliedSetpointChangeModel(Base):
    __tablename__ = "applied_setpoint_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("setpoint_recommendations.id", ondelete="CASCADE"),
        nullable=False,
    )
    building_id: Mapped[int] = mapped_column(
        ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False
    )
    zone_id: Mapped[int] = mapped_column(
        ForeignKey("zones.id", ondelete="CASCADE"), nullable=False
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    setpoint_delta_f: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    adapter_message: Mapped[str] = mapped_column(
        String(255), server_default=text("''"), nullable=False
    )
    latency_ms: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('dispatched','failed')",
            name="ck_applied_setpoint_changes_status",
        ),
        UniqueConstraint(
            "recommendation_id", name="uq_applied_setpoint_changes_rec"
        ),
        Index(
            "ix_applied_setpoint_changes_building_applied",
            "building_id",
            "applied_at",
        ),
    )
