"""add anomaly context columns to sessions

Revision ID: 20260407_0004
Revises: 20260407_0003
Create Date: 2026-04-07 19:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260407_0004"
down_revision = "20260407_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("use_case_type", sa.String(length=120), nullable=False, server_default="Smart City"),
        schema="network",
    )
    op.add_column(
        "sessions",
        sa.Column("required_mobility", sa.Boolean(), nullable=False, server_default="false"),
        schema="network",
    )
    op.add_column(
        "sessions",
        sa.Column("required_connectivity", sa.Boolean(), nullable=False, server_default="false"),
        schema="network",
    )
    op.add_column(
        "sessions",
        sa.Column("slice_handover", sa.Boolean(), nullable=False, server_default="false"),
        schema="network",
    )
    op.add_column(
        "sessions",
        sa.Column("packet_loss_budget", sa.Numeric(10, 6), nullable=False, server_default="0"),
        schema="network",
    )
    op.add_column(
        "sessions",
        sa.Column("latency_budget_ns", sa.BigInteger(), nullable=False, server_default="0"),
        schema="network",
    )
    op.add_column(
        "sessions",
        sa.Column("jitter_budget_ns", sa.BigInteger(), nullable=False, server_default="0"),
        schema="network",
    )
    op.add_column(
        "sessions",
        sa.Column("data_rate_budget_gbps", sa.Numeric(10, 2), nullable=False, server_default="0"),
        schema="network",
    )
    op.add_column(
        "sessions",
        sa.Column("slice_available_transfer_rate_gbps", sa.Numeric(12, 3), nullable=False, server_default="0"),
        schema="network",
    )
    op.add_column(
        "sessions",
        sa.Column("slice_latency_ns", sa.BigInteger(), nullable=False, server_default="0"),
        schema="network",
    )
    op.add_column(
        "sessions",
        sa.Column("slice_packet_loss", sa.Numeric(10, 6), nullable=False, server_default="0"),
        schema="network",
    )
    op.add_column(
        "sessions",
        sa.Column("slice_jitter_ns", sa.BigInteger(), nullable=False, server_default="0"),
        schema="network",
    )

    op.create_check_constraint(
        "ck_sessions_use_case_type_not_empty",
        "sessions",
        "use_case_type <> ''",
        schema="network",
    )
    op.create_check_constraint(
        "ck_sessions_packet_loss_budget_positive",
        "sessions",
        "packet_loss_budget >= 0",
        schema="network",
    )
    op.create_check_constraint(
        "ck_sessions_latency_budget_positive",
        "sessions",
        "latency_budget_ns >= 0",
        schema="network",
    )
    op.create_check_constraint(
        "ck_sessions_jitter_budget_positive",
        "sessions",
        "jitter_budget_ns >= 0",
        schema="network",
    )
    op.create_check_constraint(
        "ck_sessions_data_rate_budget_positive",
        "sessions",
        "data_rate_budget_gbps >= 0",
        schema="network",
    )
    op.create_check_constraint(
        "ck_sessions_slice_available_transfer_rate_positive",
        "sessions",
        "slice_available_transfer_rate_gbps >= 0",
        schema="network",
    )
    op.create_check_constraint(
        "ck_sessions_slice_latency_positive",
        "sessions",
        "slice_latency_ns >= 0",
        schema="network",
    )
    op.create_check_constraint(
        "ck_sessions_slice_packet_loss_positive",
        "sessions",
        "slice_packet_loss >= 0",
        schema="network",
    )
    op.create_check_constraint(
        "ck_sessions_slice_jitter_positive",
        "sessions",
        "slice_jitter_ns >= 0",
        schema="network",
    )


def downgrade() -> None:
    op.drop_constraint("ck_sessions_slice_jitter_positive", "sessions", schema="network", type_="check")
    op.drop_constraint("ck_sessions_slice_packet_loss_positive", "sessions", schema="network", type_="check")
    op.drop_constraint("ck_sessions_slice_latency_positive", "sessions", schema="network", type_="check")
    op.drop_constraint(
        "ck_sessions_slice_available_transfer_rate_positive",
        "sessions",
        schema="network",
        type_="check",
    )
    op.drop_constraint("ck_sessions_data_rate_budget_positive", "sessions", schema="network", type_="check")
    op.drop_constraint("ck_sessions_jitter_budget_positive", "sessions", schema="network", type_="check")
    op.drop_constraint("ck_sessions_latency_budget_positive", "sessions", schema="network", type_="check")
    op.drop_constraint("ck_sessions_packet_loss_budget_positive", "sessions", schema="network", type_="check")
    op.drop_constraint("ck_sessions_use_case_type_not_empty", "sessions", schema="network", type_="check")
    op.drop_column("sessions", "slice_jitter_ns", schema="network")
    op.drop_column("sessions", "slice_packet_loss", schema="network")
    op.drop_column("sessions", "slice_latency_ns", schema="network")
    op.drop_column("sessions", "slice_available_transfer_rate_gbps", schema="network")
    op.drop_column("sessions", "data_rate_budget_gbps", schema="network")
    op.drop_column("sessions", "jitter_budget_ns", schema="network")
    op.drop_column("sessions", "latency_budget_ns", schema="network")
    op.drop_column("sessions", "packet_loss_budget", schema="network")
    op.drop_column("sessions", "slice_handover", schema="network")
    op.drop_column("sessions", "required_connectivity", schema="network")
    op.drop_column("sessions", "required_mobility", schema="network")
    op.drop_column("sessions", "use_case_type", schema="network")
