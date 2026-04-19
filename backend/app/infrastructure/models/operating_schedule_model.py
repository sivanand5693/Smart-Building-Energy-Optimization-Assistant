from datetime import time
from sqlalchemy import String, Time, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class OperatingScheduleModel(Base):
    __tablename__ = "operating_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False)
    days_of_week: Mapped[str] = mapped_column(String(64), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    building: Mapped["BuildingModel"] = relationship(back_populates="operating_schedules")
