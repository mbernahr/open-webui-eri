"""add eri_secret and data field to knowledge

Revision ID: 402aa44befb6
Revises: 3e0e00844bb0
Create Date: 2025-12-11 17:15:24.162990

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = "402aa44befb6"
down_revision: Union[str, None] = "3e0e00844bb0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge", sa.Column("eri_secret", sa.JSON()))
    op.add_column("knowledge", sa.Column("data", sa.JSON()))


def downgrade() -> None:
    op.drop_column("knowledge", "eri_secret")
    op.drop_column("knowledge", "data")
