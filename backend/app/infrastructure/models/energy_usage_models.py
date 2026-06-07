"""UC9 — energy usage + daily savings report models."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class EnergyUsageRecordModel(Base):
    __tablename__ = "energy_usage_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(
        ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False
    )
    zone_id: Mapped[int] = mapped_column(
        ForeignKey("zones.id", ondelete="CASCADE"), nullable=False
    )
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    kwh: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('baseline','actual')",
            name="ck_energy_usage_records_kind",
        ),
        UniqueConstraint(
            "building_id",
            "zone_id",
            "usage_date",
            "kind",
            name="uq_energy_usage_records_building_zone_date_kind",
        ),
        Index(
            "ix_energy_usage_records_building_date",
            "building_id",
            "usage_date",
        ),
    )


class DailySavingsReportModel(Base):
    __tablename__ = "daily_savings_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(
        ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    total_baseline_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False
    )
    total_actual_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False
    )
    total_savings_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False
    )
    total_savings_pct: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False
    )
    elapsed_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    lines: Mapped[list["DailySavingsReportLineModel"]] = relationship(
        "DailySavingsReportLineModel",
        back_populates="report",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "building_id",
            "report_date",
            name="uq_daily_savings_reports_building_date",
        ),
    )


class DailySavingsReportLineModel(Base):
    __tablename__ = "daily_savings_report_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("daily_savings_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    zone_id: Mapped[int] = mapped_column(
        ForeignKey("zones.id", ondelete="CASCADE"), nullable=False
    )
    baseline_kwh: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), nullable=False
    )
    actual_kwh: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), nullable=False
    )
    savings_kwh: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), nullable=False
    )
    savings_pct: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False
    )
    anomaly_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    anomaly_reason: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )

    report: Mapped["DailySavingsReportModel"] = relationship(
        "DailySavingsReportModel", back_populates="lines"
    )

    __table_args__ = (
        Index(
            "ix_daily_savings_report_lines_report",
            "report_id",
        ),
    )
