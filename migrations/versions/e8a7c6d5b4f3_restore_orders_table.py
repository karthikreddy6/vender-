"""align the vendor migration chain with the customer service"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e8a7c6d5b4f3"
down_revision = "d53b2174aa71"
branch_labels = None
depends_on = None


def upgrade():
    for table, column, typ, default in [
        ("users", "roll_number", sa.String(), None), ("users", "campus", sa.String(), None),
        ("users", "college", sa.String(), None), ("users", "last_order_at", sa.DateTime(), None),
        ("users", "use_roll_number_as_order_token", sa.Boolean(), sa.false()),
        ("orders", "user_roll_number", sa.String(), None), ("orders", "discount_amount", sa.Numeric(10, 2), sa.text("0")),
        ("orders", "coupon_code", sa.String(), None), ("orders", "order_token", sa.String(), None),
        ("kitchen_settings", "use_roll_number_as_order_token", sa.Boolean(), sa.false()),
    ]:
        kwargs = {"nullable": True}
        if default is not None:
            kwargs.update(nullable=False, server_default=default)
        op.add_column(table, sa.Column(column, typ, **kwargs))
    op.create_index("ix_users_roll_number", "users", ["roll_number"], unique=True)
    op.create_index("ix_orders_user_roll_number", "orders", ["user_roll_number"])
    op.create_index("ix_orders_order_token", "orders", ["order_token"])
    op.create_table(
        "coupons", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(), nullable=False, unique=True), sa.Column("discount_type", sa.String(), nullable=False, server_default="PERCENT"),
        sa.Column("value", sa.Numeric(10, 2), nullable=False), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expires_at", sa.DateTime()), sa.Column("max_uses", sa.Integer()), sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_coupons_code", "coupons", ["code"], unique=True)
    op.create_table(
        "banners", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("title", sa.String(), nullable=False),
        sa.Column("image_url", sa.String(), nullable=False), sa.Column("link_url", sa.String()), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"), sa.Column("starts_at", sa.DateTime()), sa.Column("ends_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("banners")
    op.drop_index("ix_coupons_code", table_name="coupons")
    op.drop_table("coupons")
    for table, index, column in [("orders", "ix_orders_order_token", "order_token"), ("orders", "ix_orders_user_roll_number", "user_roll_number"), ("users", "ix_users_roll_number", "roll_number")]:
        op.drop_index(index, table_name=table)
        op.drop_column(table, column)
    for table, column in [("orders", "coupon_code"), ("orders", "discount_amount"), ("users", "last_order_at"), ("users", "college"), ("users", "campus"), ("users", "use_roll_number_as_order_token"), ("orders", "user_roll_number"), ("kitchen_settings", "use_roll_number_as_order_token")]:
        op.drop_column(table, column)
