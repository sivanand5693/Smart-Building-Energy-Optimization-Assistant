from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class ZoneComfortConstraintModel(Base):
    __tablename__ = "zone_comfort_constraints"

    zone_id: Mapped[int] = mapped_column(
        ForeignKey("zones.id", ondelete="CASCADE"), primary_key=True
    )
    min_setpoint_f: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    max_setpoint_f: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    occupied_min_f: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    occupied_max_f: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    unoccupied_min_f: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    unoccupied_max_f: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
