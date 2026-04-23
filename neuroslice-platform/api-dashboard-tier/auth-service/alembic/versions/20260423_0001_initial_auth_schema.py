from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260423_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS auth")

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", name="uq_auth_roles_name"),
        schema="auth",
    )

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("auth.roles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="auth",
    )
    op.create_index("ix_auth_users_email", "users", ["email"], unique=True, schema="auth")

    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="auth",
    )
    op.create_index("ix_auth_user_sessions_user_id", "user_sessions", ["user_id"], unique=False, schema="auth")
    op.create_index(
        "ix_auth_user_sessions_refresh_token_hash",
        "user_sessions",
        ["refresh_token_hash"],
        unique=False,
        schema="auth",
    )
    op.create_index("ix_auth_user_sessions_expires_at", "user_sessions", ["expires_at"], unique=False, schema="auth")

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("actor_user_id", sa.BigInteger(), sa.ForeignKey("auth.users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_user_id", sa.BigInteger(), sa.ForeignKey("auth.users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="auth",
    )
    op.create_index("ix_auth_audit_logs_created_at", "audit_logs", ["created_at"], unique=False, schema="auth")

    op.execute(
        sa.text(
            """
            INSERT INTO auth.roles (name, description)
            VALUES
                ('ADMIN', 'Platform administrator'),
                ('NETWORK_OPERATOR', 'NOC operator'),
                ('NETWORK_MANAGER', 'Network manager'),
                ('DATA_MLOPS_ENGINEER', 'Data and MLOps engineer')
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_auth_audit_logs_created_at", table_name="audit_logs", schema="auth")
    op.drop_table("audit_logs", schema="auth")

    op.drop_index("ix_auth_user_sessions_expires_at", table_name="user_sessions", schema="auth")
    op.drop_index("ix_auth_user_sessions_refresh_token_hash", table_name="user_sessions", schema="auth")
    op.drop_index("ix_auth_user_sessions_user_id", table_name="user_sessions", schema="auth")
    op.drop_table("user_sessions", schema="auth")

    op.drop_index("ix_auth_users_email", table_name="users", schema="auth")
    op.drop_table("users", schema="auth")

    op.drop_table("roles", schema="auth")
    op.execute("DROP SCHEMA IF EXISTS auth CASCADE")
