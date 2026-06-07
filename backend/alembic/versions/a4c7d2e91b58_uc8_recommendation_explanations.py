"""UC8 recommendation_explanations

Revision ID: a4c7d2e91b58
Revises: f9b3e7a82c41
Create Date: 2026-06-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4c7d2e91b58"
down_revision: Union[str, None] = "f9b3e7a82c41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recommendation_explanations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("factors_json", sa.JSON(), nullable=False),
        sa.Column(
            "elapsed_ms",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            ["setpoint_recommendations.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "recommendation_id",
            name="uq_recommendation_explanations_recommendation",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recommendation_explanations_recommendation",
        "recommendation_explanations",
        ["recommendation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recommendation_explanations_recommendation",
        table_name="recommendation_explanations",
    )
    op.drop_table("recommendation_explanations")
