"""widen slice category range

Revision ID: 20260407_0007
Revises: 20260407_0006
Create Date: 2026-04-07 23:20:00
"""

from __future__ import annotations

from alembic import op


revision = "20260407_0007"
down_revision = "20260407_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_sessions_lte_5g_category_range", "sessions", schema="network", type_="check")
    op.create_check_constraint(
        "ck_sessions_lte_5g_category_range",
        "sessions",
        "lte_5g_category >= 1 AND lte_5g_category <= 22",
        schema="network",
    )


def downgrade() -> None:
    op.drop_constraint("ck_sessions_lte_5g_category_range", "sessions", schema="network", type_="check")
    op.create_check_constraint(
        "ck_sessions_lte_5g_category_range",
        "sessions",
        "lte_5g_category >= 1 AND lte_5g_category <= 20",
        schema="network",
    )
