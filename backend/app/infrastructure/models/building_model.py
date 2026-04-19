from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class BuildingModel(Base):
    __tablename__ = "buildings"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    zones: Mapped[list["ZoneModel"]] = relationship(
        back_populates="building", cascade="all, delete-orphan"
    )
    operating_schedules: Mapped[list["OperatingScheduleModel"]] = relationship(
        back_populates="building", cascade="all, delete-orphan"
    )
