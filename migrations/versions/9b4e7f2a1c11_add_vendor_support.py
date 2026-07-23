"""add vendor accounts and vendor inventory fields"""

from alembic import op
import sqlalchemy as sa

revision = "9b4e7f2a1c11"
down_revision = "7f3b2c1d9a44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vendor_accounts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="staff"),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_vendor_accounts_email", "vendor_accounts", ["email"], unique=True)
    op.create_table(
        "staff_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("image_url", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("menu_items", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("menu_items", sa.Column("stock", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("menu_items", sa.Column("is_student_visible", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column("menu_items", "is_student_visible")
    op.drop_column("menu_items", "stock")
    op.drop_column("menu_items", "description")
    op.drop_table("staff_members")
    op.drop_index("ix_vendor_accounts_email", table_name="vendor_accounts")
    op.drop_table("vendor_accounts")
