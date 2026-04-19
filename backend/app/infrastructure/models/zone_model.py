from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class ZoneModel(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    building: Mapped["BuildingModel"] = relationship(back_populates="zones")
    devices: Mapped[list["DeviceModel"]] = relationship(
        back_populates="zone", cascade="all, delete-orphan"
    )
