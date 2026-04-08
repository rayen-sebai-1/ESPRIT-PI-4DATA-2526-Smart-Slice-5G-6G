"""add sla context columns to sessions

Revision ID: 20260407_0002
Revises: 20260407_0001
Create Date: 2026-04-07 17:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260407_0002"
down_revision = "20260407_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("iot_devices", sa.Integer(), nullable=False, server_default="0"),
        schema="network",
    )
    op.add_column(
        "sessions",
        sa.Column("public_safety", sa.Integer(), nullable=False, server_default="0"),
        schema="network",
    )
    op.add_column(
        "sessions",
        sa.Column("smart_city_home", sa.Integer(), nullable=False, server_default="0"),
        schema="network",
    )

    op.create_check_constraint(
        "ck_sessions_iot_devices_binary",
        "sessions",
        "iot_devices IN (0, 1)",
        schema="network",
    )
    op.create_check_constraint(
        "ck_sessions_public_safety_binary",
        "sessions",
        "public_safety IN (0, 1)",
        schema="network",
    )
    op.create_check_constraint(
        "ck_sessions_smart_city_home_binary",
        "sessions",
        "smart_city_home IN (0, 1)",
        schema="network",
    )


def downgrade() -> None:
    op.drop_constraint("ck_sessions_smart_city_home_binary", "sessions", schema="network", type_="check")
    op.drop_constraint("ck_sessions_public_safety_binary", "sessions", schema="network", type_="check")
    op.drop_constraint("ck_sessions_iot_devices_binary", "sessions", schema="network", type_="check")
    op.drop_column("sessions", "smart_city_home", schema="network")
    op.drop_column("sessions", "public_safety", schema="network")
    op.drop_column("sessions", "iot_devices", schema="network")
