"""Add mlops_retraining_schedules table

Revision ID: 20260503_0005
Revises: 20260430_0004
Create Date: 2026-05-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260503_0005"
down_revision = "20260430_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mlops_retraining_schedules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("frequency", sa.String(length=32), nullable=False),
        sa.Column("cron_expr", sa.String(length=128), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default=sa.text("'UTC'")),
        sa.Column("require_approval", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.PrimaryKeyConstraint("id"),
        schema="dashboard",
    )
    op.create_index(
        "ix_dashboard_mlops_retraining_schedules_enabled_next",
        "mlops_retraining_schedules",
        ["enabled", "next_run_at"],
        unique=False,
        schema="dashboard",
    )
    op.create_index(
        "ix_dashboard_mlops_retraining_schedules_model",
        "mlops_retraining_schedules",
        ["model_name"],
        unique=False,
        schema="dashboard",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dashboard_mlops_retraining_schedules_model",
        table_name="mlops_retraining_schedules",
        schema="dashboard",
    )
    op.drop_index(
        "ix_dashboard_mlops_retraining_schedules_enabled_next",
        table_name="mlops_retraining_schedules",
        schema="dashboard",
    )
    op.drop_table("mlops_retraining_schedules", schema="dashboard")
