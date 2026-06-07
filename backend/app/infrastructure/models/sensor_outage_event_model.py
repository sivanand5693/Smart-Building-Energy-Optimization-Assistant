"""UC10 sensor_outage_events model."""
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class SensorOutageEventModel(Base):
    __tablename__ = "sensor_outage_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(
        ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False
    )
    declared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    affected_zone_ids: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint(
            "decision IN ('fallback','paused')",
            name="ck_sensor_outage_events_decision",
        ),
        Index(
            "ix_sensor_outage_events_building_declared",
            "building_id",
            "declared_at",
        ),
    )
