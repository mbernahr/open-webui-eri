"""merge heads (ERI + v0.8.3)

Revision ID: 4a6be5cf79c1
Revises: 402aa44befb6, b2c3d4e5f6a7
Create Date: 2026-02-18 13:31:27.404163

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = '4a6be5cf79c1'
down_revision: Union[str, None] = ('402aa44befb6', 'b2c3d4e5f6a7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
