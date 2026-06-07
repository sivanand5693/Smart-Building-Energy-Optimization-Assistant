"""UC6 plan_adaptation_events

Revision ID: e8a5c4d62a7f
Revises: c7d2a1f9e5b0
Create Date: 2026-06-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8a5c4d62a7f"
down_revision: Union[str, None] = "c7d2a1f9e5b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plan_adaptation_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("building_id", sa.Integer(), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column(
            "reason",
            sa.Text(),
            server_default=sa.text("''"),
            nullable=False,
        ),
        sa.Column(
            "active_plan_run_timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "new_run_timestamp",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "changed_zone_ids",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column(
            "elapsed_ms",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "decision IN ('replanned','no_replan')",
            name="ck_plan_adaptation_events_decision",
        ),
        sa.ForeignKeyConstraint(
            ["building_id"], ["buildings.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_plan_adaptation_events_building_requested",
        "plan_adaptation_events",
        ["building_id", sa.text("requested_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_plan_adaptation_events_building_requested",
        table_name="plan_adaptation_events",
    )
    op.drop_table("plan_adaptation_events")
