"""add slice classifier context to sessions

Revision ID: 20260407_0006
Revises: 20260407_0005
Create Date: 2026-04-07 21:35:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260407_0006"
down_revision = "20260407_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("lte_5g_category", sa.Integer(), nullable=False, server_default="10"),
        schema="network",
    )
    op.add_column(
        "sessions",
        sa.Column("smartphone", sa.Integer(), nullable=False, server_default="0"),
        schema="network",
    )
    op.add_column(
        "sessions",
        sa.Column("gbr", sa.Integer(), nullable=False, server_default="0"),
        schema="network",
    )

    op.create_check_constraint(
        "ck_sessions_lte_5g_category_range",
        "sessions",
        "lte_5g_category >= 1 AND lte_5g_category <= 20",
        schema="network",
    )
    op.create_check_constraint(
        "ck_sessions_smartphone_binary",
        "sessions",
        "smartphone IN (0, 1)",
        schema="network",
    )
    op.create_check_constraint(
        "ck_sessions_gbr_binary",
        "sessions",
        "gbr IN (0, 1)",
        schema="network",
    )


def downgrade() -> None:
    op.drop_constraint("ck_sessions_gbr_binary", "sessions", schema="network", type_="check")
    op.drop_constraint("ck_sessions_smartphone_binary", "sessions", schema="network", type_="check")
    op.drop_constraint("ck_sessions_lte_5g_category_range", "sessions", schema="network", type_="check")

    op.drop_column("sessions", "gbr", schema="network")
    op.drop_column("sessions", "smartphone", schema="network")
    op.drop_column("sessions", "lte_5g_category", schema="network")
