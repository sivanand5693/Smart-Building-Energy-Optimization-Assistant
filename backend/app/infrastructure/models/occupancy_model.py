from datetime import datetime
from sqlalchemy import Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class OccupancyRecordModel(Base):
    __tablename__ = "occupancy_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    zone_id: Mapped[int] = mapped_column(
        ForeignKey("zones.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    occupancy_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    zone: Mapped["ZoneModel"] = relationship()
