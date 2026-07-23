"""add campus, college, canteen, and tenant scoping"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f1a2b3c4d5e6"
down_revision = "e8a7c6d5b4f3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("campuses", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("name", sa.String(), nullable=False, unique=True), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table("colleges", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("campus_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campuses.id"), nullable=False), sa.Column("name", sa.String(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table("canteens", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("campus_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campuses.id"), nullable=False), sa.Column("name", sa.String(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table("college_canteens", sa.Column("college_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("colleges.id", ondelete="CASCADE"), primary_key=True), sa.Column("canteen_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("canteens.id", ondelete="CASCADE"), primary_key=True))
    for table, column, ref in [("users", "campus_id", "campuses.id"), ("users", "college_id", "colleges.id"), ("users", "preferred_canteen_id", "canteens.id"), ("vendor_accounts", "canteen_id", "canteens.id"), ("staff_members", "canteen_id", "canteens.id"), ("menu_items", "canteen_id", "canteens.id"), ("cart_items", "canteen_id", "canteens.id"), ("orders", "canteen_id", "canteens.id"), ("banners", "campus_id", "campuses.id"), ("banners", "college_id", "colleges.id"), ("banners", "canteen_id", "canteens.id")]:
        op.add_column(table, sa.Column(column, postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(None, table, ref.split('.')[0], [column], [ref.split('.')[1]])


def downgrade():
    for table, column in [("banners", "canteen_id"), ("banners", "college_id"), ("banners", "campus_id"), ("orders", "canteen_id"), ("cart_items", "canteen_id"), ("menu_items", "canteen_id"), ("staff_members", "canteen_id"), ("vendor_accounts", "canteen_id"), ("users", "preferred_canteen_id"), ("users", "college_id"), ("users", "campus_id")]:
        op.drop_column(table, column)
    op.drop_table("college_canteens"); op.drop_table("canteens"); op.drop_table("colleges"); op.drop_table("campuses")
