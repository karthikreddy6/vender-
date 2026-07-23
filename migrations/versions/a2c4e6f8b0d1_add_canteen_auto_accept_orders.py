"""add per-canteen vendor auto-accept setting

Revision ID: a2c4e6f8b0d1
Revises: f1a2b3c4d5e6
"""
from alembic import op
import sqlalchemy as sa


revision = "a2c4e6f8b0d1"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("canteens", sa.Column("auto_accept_orders", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("canteens", "auto_accept_orders")
