"""add_cancelled_and_rejected_statuses

Revision ID: 405afd84e953
Revises: a2c4e6f8b0d1
Create Date: 2026-07-24 12:07:45.493924

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '405afd84e953'
down_revision: Union[str, Sequence[str], None] = 'a2c4e6f8b0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # End current transaction block since ALTER TYPE ADD VALUE cannot run inside transactions
    op.execute("COMMIT")
    
    bind = op.get_bind()
    
    # Check if 'CANCELLED' already exists
    cancelled_exists = bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE pg_type.typname = 'order_status' AND pg_enum.enumlabel = 'CANCELLED')"
    )).scalar()
    if not cancelled_exists:
        op.execute("ALTER TYPE order_status ADD VALUE 'CANCELLED'")
        
    # Check if 'REJECTED' already exists
    rejected_exists = bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE pg_type.typname = 'order_status' AND pg_enum.enumlabel = 'REJECTED')"
    )).scalar()
    if not rejected_exists:
        op.execute("ALTER TYPE order_status ADD VALUE 'REJECTED'")


def downgrade() -> None:
    """Downgrade schema (no-op as removing enum values is not supported in PostgreSQL)."""
    pass
