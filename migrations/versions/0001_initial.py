"""initial monetization schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _existing_tables():
    """Names of tables already present in the target schema."""
    bind = op.get_bind()
    return set(sa.inspect(bind).get_table_names())


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # Some tables (notably `conversations`) may already have been created
    # outside Alembic by backend/storage.py's CREATE TABLE IF NOT EXISTS on a
    # previous deploy. Skip those instead of failing with DuplicateTable.
    existing = _existing_tables()

    if "users" not in existing:
        op.create_table(
            "users",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("google_sub", sa.Text(), nullable=False, unique=True),
            sa.Column("email", sa.Text(), nullable=False, unique=True),
            sa.Column("display_name", sa.Text()),
            sa.Column("avatar_url", sa.Text()),
            sa.Column("role", sa.Text(), nullable=False, server_default="user"),
            sa.Column("credits", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("last_login_at", sa.DateTime(timezone=True)),
        )

    if "credit_transactions" not in existing:
        op.create_table(
            "credit_transactions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("kind", sa.Text(), nullable=False),
            sa.Column("paypal_order_id", sa.Text()),
            sa.Column("paypal_capture_id", sa.Text()),
            sa.Column("conversation_id", sa.Text()),
            sa.Column("reason", sa.Text()),
            sa.Column("balance_after", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_tx_paypal_order "
        "ON credit_transactions (paypal_order_id) "
        "WHERE paypal_order_id IS NOT NULL"
    )

    if "app_settings" not in existing:
        op.create_table(
            "app_settings",
            sa.Column("key", sa.Text(), primary_key=True),
            sa.Column("value", postgresql.JSONB(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        )

    if "conversations" not in existing:
        op.create_table(
            "conversations",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("user_id", sa.Text()),
            sa.Column("data", postgresql.JSONB(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )


def downgrade():
    op.drop_table("conversations")
    op.drop_table("app_settings")
    op.drop_table("credit_transactions")
    op.drop_table("users")
