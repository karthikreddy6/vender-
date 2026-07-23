"""add_menu_sync_timestamps

Revision ID: 7f3b2c1d9a44
Revises: d53b2174aa71
Create Date: 2026-07-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7f3b2c1d9a44"
down_revision: Union[str, Sequence[str], None] = "d53b2174aa71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.add_column(
        "menu_items",
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("ix_categories_updated_at", "categories", ["updated_at"])
    op.create_index("ix_menu_items_updated_at", "menu_items", ["updated_at"])
    op.create_index("ix_menu_items_category_available", "menu_items", ["category_id", "is_available"])


def downgrade() -> None:
    op.drop_index("ix_menu_items_category_available", table_name="menu_items")
    op.drop_index("ix_menu_items_updated_at", table_name="menu_items")
    op.drop_index("ix_categories_updated_at", table_name="categories")
    op.drop_column("menu_items", "updated_at")
    op.drop_column("categories", "updated_at")
