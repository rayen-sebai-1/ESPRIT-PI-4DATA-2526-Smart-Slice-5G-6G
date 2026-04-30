"""Add trigger_source column to mlops_orchestration_runs

Revision ID: 20260430_0004
Revises: 20260428_0003
Create Date: 2026-04-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260430_0004"
down_revision = "20260428_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mlops_orchestration_runs",
        sa.Column(
            "trigger_source",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'manual'"),
        ),
        schema="dashboard",
    )


def downgrade() -> None:
    op.drop_column("mlops_orchestration_runs", "trigger_source", schema="dashboard")
