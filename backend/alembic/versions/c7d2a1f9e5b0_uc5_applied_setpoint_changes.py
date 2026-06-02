"""UC5 applied_setpoint_changes

Revision ID: c7d2a1f9e5b0
Revises: a91c2f3d7e84
Create Date: 2026-06-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7d2a1f9e5b0"
down_revision: Union[str, None] = "a91c2f3d7e84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "applied_setpoint_changes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=False),
        sa.Column("building_id", sa.Integer(), nullable=False),
        sa.Column("zone_id", sa.Integer(), nullable=False),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "setpoint_delta_f", sa.Numeric(precision=5, scale=2), nullable=False
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column(
            "adapter_message",
            sa.String(length=255),
            server_default=sa.text("''"),
            nullable=False,
        ),
        sa.Column(
            "latency_ms",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('dispatched','failed')",
            name="ck_applied_setpoint_changes_status",
        ),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            ["setpoint_recommendations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["building_id"], ["buildings.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "recommendation_id", name="uq_applied_setpoint_changes_rec"
        ),
    )
    op.create_index(
        "ix_applied_setpoint_changes_building_applied",
        "applied_setpoint_changes",
        ["building_id", "applied_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_applied_setpoint_changes_building_applied",
        table_name="applied_setpoint_changes",
    )
    op.drop_table("applied_setpoint_changes")
