"""UC7 comfort_risk_runs + comfort_risk_alerts

Revision ID: f9b3e7a82c41
Revises: e8a5c4d62a7f
Create Date: 2026-06-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f9b3e7a82c41"
down_revision: Union[str, None] = "e8a5c4d62a7f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "comfort_risk_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("building_id", sa.Integer(), nullable=False),
        sa.Column(
            "run_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(length=8), nullable=False),
        sa.Column(
            "alerts_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "elapsed_ms",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "source_run_timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "decision IN ('alert','pass')",
            name="ck_comfort_risk_runs_decision",
        ),
        sa.ForeignKeyConstraint(
            ["building_id"], ["buildings.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_comfort_risk_runs_building_run_at",
        "comfort_risk_runs",
        ["building_id", sa.text("run_at DESC")],
        unique=False,
    )

    op.create_table(
        "comfort_risk_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("zone_id", sa.Integer(), nullable=False),
        sa.Column("projected_temp_f", sa.Numeric(5, 2), nullable=False),
        sa.Column("occupied_min_f", sa.Numeric(5, 2), nullable=False),
        sa.Column("occupied_max_f", sa.Numeric(5, 2), nullable=False),
        sa.Column("risk_score", sa.Numeric(4, 3), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("mitigation", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "direction IN ('above','below')",
            name="ck_comfort_risk_alerts_direction",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["comfort_risk_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["zone_id"], ["zones.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_comfort_risk_alerts_run",
        "comfort_risk_alerts",
        ["run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_comfort_risk_alerts_run", table_name="comfort_risk_alerts")
    op.drop_table("comfort_risk_alerts")
    op.drop_index(
        "ix_comfort_risk_runs_building_run_at", table_name="comfort_risk_runs"
    )
    op.drop_table("comfort_risk_runs")
