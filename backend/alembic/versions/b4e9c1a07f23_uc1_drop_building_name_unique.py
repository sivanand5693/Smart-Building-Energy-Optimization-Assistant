"""UC1 drop unique constraint on buildings.name

Revision ID: b4e9c1a07f23
Revises: 1a325eb44672
Create Date: 2026-05-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b4e9c1a07f23'
down_revision: Union[str, None] = '1a325eb44672'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("buildings_name_key", "buildings", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint("buildings_name_key", "buildings", ["name"])
