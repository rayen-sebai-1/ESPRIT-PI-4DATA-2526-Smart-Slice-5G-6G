"""add congestion context columns to sessions

Revision ID: 20260407_0003
Revises: 20260407_0002
Create Date: 2026-04-07 18:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260407_0003"
down_revision = "20260407_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("cpu_util_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        schema="network",
    )
    op.add_column(
        "sessions",
        sa.Column("mem_util_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        schema="network",
    )
    op.add_column(
        "sessions",
        sa.Column("bw_util_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        schema="network",
    )
    op.add_column(
        "sessions",
        sa.Column("active_users", sa.Integer(), nullable=False, server_default="0"),
        schema="network",
    )
    op.add_column(
        "sessions",
        sa.Column("queue_len", sa.Integer(), nullable=False, server_default="0"),
        schema="network",
    )

    op.create_check_constraint(
        "ck_sessions_cpu_util_pct_range",
        "sessions",
        "cpu_util_pct >= 0 AND cpu_util_pct <= 100",
        schema="network",
    )
    op.create_check_constraint(
        "ck_sessions_mem_util_pct_range",
        "sessions",
        "mem_util_pct >= 0 AND mem_util_pct <= 100",
        schema="network",
    )
    op.create_check_constraint(
        "ck_sessions_bw_util_pct_range",
        "sessions",
        "bw_util_pct >= 0 AND bw_util_pct <= 100",
        schema="network",
    )
    op.create_check_constraint(
        "ck_sessions_active_users_positive",
        "sessions",
        "active_users >= 0",
        schema="network",
    )
    op.create_check_constraint(
        "ck_sessions_queue_len_positive",
        "sessions",
        "queue_len >= 0",
        schema="network",
    )


def downgrade() -> None:
    op.drop_constraint("ck_sessions_queue_len_positive", "sessions", schema="network", type_="check")
    op.drop_constraint("ck_sessions_active_users_positive", "sessions", schema="network", type_="check")
    op.drop_constraint("ck_sessions_bw_util_pct_range", "sessions", schema="network", type_="check")
    op.drop_constraint("ck_sessions_mem_util_pct_range", "sessions", schema="network", type_="check")
    op.drop_constraint("ck_sessions_cpu_util_pct_range", "sessions", schema="network", type_="check")
    op.drop_column("sessions", "queue_len", schema="network")
    op.drop_column("sessions", "active_users", schema="network")
    op.drop_column("sessions", "bw_util_pct", schema="network")
    op.drop_column("sessions", "mem_util_pct", schema="network")
    op.drop_column("sessions", "cpu_util_pct", schema="network")
