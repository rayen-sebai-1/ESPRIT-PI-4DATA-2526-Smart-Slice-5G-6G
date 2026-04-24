from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260423_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS dashboard")

    op.create_table(
        "dashboard_preferences",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False, server_default=sa.text("'me'")),
        sa.Column("preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="dashboard",
    )
    op.create_index(
        "ix_dashboard_preferences_user_id_scope",
        "dashboard_preferences",
        ["user_id", "scope"],
        unique=True,
        schema="dashboard",
    )

    op.create_table(
        "dashboard_bookmarks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_key", sa.String(length=255), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="dashboard",
    )
    op.create_index(
        "ix_dashboard_bookmarks_user_resource_key",
        "dashboard_bookmarks",
        ["user_id", "resource_key"],
        unique=True,
        schema="dashboard",
    )

    op.create_table(
        "alert_acknowledgements",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alert_key", sa.String(length=255), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="dashboard",
    )
    op.create_index(
        "ix_dashboard_alert_acknowledgements_alert_user",
        "alert_acknowledgements",
        ["alert_key", "user_id"],
        unique=True,
        schema="dashboard",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dashboard_alert_acknowledgements_alert_user",
        table_name="alert_acknowledgements",
        schema="dashboard",
    )
    op.drop_table("alert_acknowledgements", schema="dashboard")

    op.drop_index("ix_dashboard_bookmarks_user_resource_key", table_name="dashboard_bookmarks", schema="dashboard")
    op.drop_table("dashboard_bookmarks", schema="dashboard")

    op.drop_index("ix_dashboard_preferences_user_id_scope", table_name="dashboard_preferences", schema="dashboard")
    op.drop_table("dashboard_preferences", schema="dashboard")

    op.execute("DROP SCHEMA IF EXISTS dashboard CASCADE")
