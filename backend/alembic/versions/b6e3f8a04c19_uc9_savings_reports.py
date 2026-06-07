"""UC9 savings reports + energy usage records

Revision ID: b6e3f8a04c19
Revises: a4c7d2e91b58
Create Date: 2026-06-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b6e3f8a04c19"
down_revision: Union[str, None] = "a4c7d2e91b58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "energy_usage_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("building_id", sa.Integer(), nullable=False),
        sa.Column("zone_id", sa.Integer(), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("kwh", sa.Numeric(10, 3), nullable=False),
        sa.ForeignKeyConstraint(
            ["building_id"], ["buildings.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["zone_id"], ["zones.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "kind IN ('baseline','actual')",
            name="ck_energy_usage_records_kind",
        ),
        sa.UniqueConstraint(
            "building_id",
            "zone_id",
            "usage_date",
            "kind",
            name="uq_energy_usage_records_building_zone_date_kind",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_energy_usage_records_building_date",
        "energy_usage_records",
        ["building_id", "usage_date"],
        unique=False,
    )

    op.create_table(
        "daily_savings_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("building_id", sa.Integer(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("total_baseline_kwh", sa.Numeric(12, 3), nullable=False),
        sa.Column("total_actual_kwh", sa.Numeric(12, 3), nullable=False),
        sa.Column("total_savings_kwh", sa.Numeric(12, 3), nullable=False),
        sa.Column("total_savings_pct", sa.Numeric(6, 2), nullable=False),
        sa.Column(
            "elapsed_ms",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["building_id"], ["buildings.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "building_id",
            "report_date",
            name="uq_daily_savings_reports_building_date",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "daily_savings_report_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("zone_id", sa.Integer(), nullable=False),
        sa.Column("baseline_kwh", sa.Numeric(10, 3), nullable=False),
        sa.Column("actual_kwh", sa.Numeric(10, 3), nullable=False),
        sa.Column("savings_kwh", sa.Numeric(10, 3), nullable=False),
        sa.Column("savings_pct", sa.Numeric(6, 2), nullable=False),
        sa.Column(
            "anomaly_flag",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("anomaly_reason", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["daily_savings_reports.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["zone_id"], ["zones.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_daily_savings_report_lines_report",
        "daily_savings_report_lines",
        ["report_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_daily_savings_report_lines_report",
        table_name="daily_savings_report_lines",
    )
    op.drop_table("daily_savings_report_lines")
    op.drop_table("daily_savings_reports")
    op.drop_index(
        "ix_energy_usage_records_building_date",
        table_name="energy_usage_records",
    )
    op.drop_table("energy_usage_records")
