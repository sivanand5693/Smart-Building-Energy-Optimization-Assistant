"""UC10 sensor outage events + degraded_confidence columns

Revision ID: d1f2a3b4c5d6
Revises: b6e3f8a04c19
Create Date: 2026-06-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1f2a3b4c5d6"
down_revision: Union[str, None] = "b6e3f8a04c19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "demand_forecasts",
        sa.Column(
            "degraded_confidence",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "setpoint_recommendations",
        sa.Column(
            "degraded_confidence",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    op.create_table(
        "sensor_outage_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("building_id", sa.Integer(), nullable=False),
        sa.Column(
            "declared_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "affected_zone_ids",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column(
            "reason",
            sa.Text(),
            server_default=sa.text("''"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column(
            "notes",
            sa.Text(),
            server_default=sa.text("''"),
            nullable=False,
        ),
        sa.Column(
            "elapsed_ms",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["building_id"], ["buildings.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "decision IN ('fallback','paused')",
            name="ck_sensor_outage_events_decision",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sensor_outage_events_building_declared",
        "sensor_outage_events",
        ["building_id", sa.text("declared_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sensor_outage_events_building_declared",
        table_name="sensor_outage_events",
    )
    op.drop_table("sensor_outage_events")
    op.drop_column("setpoint_recommendations", "degraded_confidence")
    op.drop_column("demand_forecasts", "degraded_confidence")
