"""UC4 zone_comfort_constraints + setpoint_recommendations

Revision ID: a91c2f3d7e84
Revises: b4e9c1a07f23
Create Date: 2026-06-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a91c2f3d7e84"
down_revision: Union[str, None] = "b4e9c1a07f23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "zone_comfort_constraints",
        sa.Column("zone_id", sa.Integer(), nullable=False),
        sa.Column("min_setpoint_f", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("max_setpoint_f", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("occupied_min_f", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("occupied_max_f", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column(
            "unoccupied_min_f", sa.Numeric(precision=5, scale=2), nullable=False
        ),
        sa.Column(
            "unoccupied_max_f", sa.Numeric(precision=5, scale=2), nullable=False
        ),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("zone_id"),
    )

    op.create_table(
        "setpoint_recommendations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("building_id", sa.Integer(), nullable=False),
        sa.Column("zone_id", sa.Integer(), nullable=False),
        sa.Column("run_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "setpoint_delta_f", sa.Numeric(precision=5, scale=2), nullable=False
        ),
        sa.Column(
            "projected_savings_kwh",
            sa.Numeric(precision=10, scale=3),
            nullable=False,
        ),
        sa.Column("comfort_impact", sa.String(length=16), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "comfort_impact IN ('none','minor','moderate')",
            name="ck_setpoint_recommendations_comfort_impact",
        ),
        sa.CheckConstraint(
            "projected_savings_kwh >= 0",
            name="ck_setpoint_recommendations_savings_nonneg",
        ),
        sa.CheckConstraint(
            "rank >= 1", name="ck_setpoint_recommendations_rank_positive"
        ),
        sa.ForeignKeyConstraint(
            ["building_id"], ["buildings.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_setpoint_recommendations_building_run",
        "setpoint_recommendations",
        ["building_id", "run_timestamp"],
        unique=False,
    )
    op.create_index(
        "ix_setpoint_recommendations_building_run_rank",
        "setpoint_recommendations",
        ["building_id", "run_timestamp", "rank"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_setpoint_recommendations_building_run_rank",
        table_name="setpoint_recommendations",
    )
    op.drop_index(
        "ix_setpoint_recommendations_building_run",
        table_name="setpoint_recommendations",
    )
    op.drop_table("setpoint_recommendations")
    op.drop_table("zone_comfort_constraints")
