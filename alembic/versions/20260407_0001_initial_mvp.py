"""initial mvp schema

Revision ID: 20260407_0001
Revises:
Create Date: 2026-04-07 14:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260407_0001"
down_revision = None
branch_labels = None
depends_on = None


user_role_enum = postgresql.ENUM(
    "ADMIN",
    "NETWORK_OPERATOR",
    "NETWORK_MANAGER",
    name="user_role",
    create_type=False,
)

ric_status_enum = postgresql.ENUM(
    "HEALTHY",
    "DEGRADED",
    "CRITICAL",
    "MAINTENANCE",
    name="ric_status",
    create_type=False,
)

slice_type_enum = postgresql.ENUM(
    "eMBB",
    "URLLC",
    "mMTC",
    "ERLLC",
    "feMBB",
    "umMTC",
    "MBRLLC",
    "mURLLC",
    name="slice_type",
    create_type=False,
)

risk_level_enum = postgresql.ENUM(
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL",
    name="risk_level",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    op.execute("CREATE SCHEMA IF NOT EXISTS auth")
    op.execute("CREATE SCHEMA IF NOT EXISTS network")
    op.execute("CREATE SCHEMA IF NOT EXISTS monitoring")
    op.execute("CREATE SCHEMA IF NOT EXISTS dashboard")

    user_role_enum.create(bind, checkfirst=True)
    ric_status_enum.create(bind, checkfirst=True)
    slice_type_enum.create(bind, checkfirst=True)
    risk_level_enum.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", user_role_enum, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("email", name="uq_auth_users_email"),
        schema="auth",
    )
    op.create_index("ix_auth_users_role", "users", ["role"], unique=False, schema="auth")
    op.create_index("ix_auth_users_is_active", "users", ["is_active"], unique=False, schema="auth")

    op.create_table(
        "regions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("ric_status", ric_status_enum, nullable=False),
        sa.Column("network_load", sa.Numeric(5, 2), nullable=False),
        sa.Column("gnodeb_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("network_load >= 0 AND network_load <= 100", name="ck_regions_network_load_range"),
        sa.CheckConstraint("gnodeb_count >= 0", name="ck_regions_gnodeb_count_positive"),
        sa.UniqueConstraint("code", name="uq_network_regions_code"),
        sa.UniqueConstraint("name", name="uq_network_regions_name"),
        schema="network",
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("session_code", sa.String(length=64), nullable=False),
        sa.Column("region_id", sa.BigInteger(), nullable=False),
        sa.Column("slice_type", slice_type_enum, nullable=False),
        sa.Column("latency_ms", sa.Numeric(10, 2), nullable=False),
        sa.Column("packet_loss", sa.Numeric(6, 3), nullable=False),
        sa.Column("throughput_mbps", sa.Numeric(10, 2), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("latency_ms >= 0", name="ck_sessions_latency_positive"),
        sa.CheckConstraint("packet_loss >= 0", name="ck_sessions_packet_loss_positive"),
        sa.CheckConstraint("throughput_mbps >= 0", name="ck_sessions_throughput_positive"),
        sa.ForeignKeyConstraint(["region_id"], ["network.regions.id"], name="fk_sessions_region_id", ondelete="RESTRICT"),
        sa.UniqueConstraint("session_code", name="uq_network_sessions_session_code"),
        schema="network",
    )
    op.create_index("ix_network_sessions_region_id", "sessions", ["region_id"], unique=False, schema="network")
    op.create_index("ix_network_sessions_slice_type", "sessions", ["slice_type"], unique=False, schema="network")
    op.create_index(
        "ix_network_sessions_region_timestamp",
        "sessions",
        ["region_id", "timestamp"],
        unique=False,
        schema="network",
    )

    op.create_table(
        "predictions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("sla_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("congestion_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("anomaly_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("risk_level", risk_level_enum, nullable=False),
        sa.Column("predicted_slice_type", slice_type_enum, nullable=False),
        sa.Column("slice_confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("model_source", sa.String(length=120), nullable=False),
        sa.Column("predicted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("sla_score >= 0 AND sla_score <= 1", name="ck_predictions_sla_score_range"),
        sa.CheckConstraint(
            "congestion_score >= 0 AND congestion_score <= 1",
            name="ck_predictions_congestion_score_range",
        ),
        sa.CheckConstraint("anomaly_score >= 0 AND anomaly_score <= 1", name="ck_predictions_anomaly_score_range"),
        sa.CheckConstraint(
            "slice_confidence >= 0 AND slice_confidence <= 1",
            name="ck_predictions_slice_confidence_range",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["network.sessions.id"],
            name="fk_predictions_session_id",
            ondelete="CASCADE",
        ),
        schema="monitoring",
    )
    op.create_index(
        "ix_monitoring_predictions_session_predicted_at",
        "predictions",
        ["session_id", "predicted_at"],
        unique=False,
        schema="monitoring",
    )
    op.create_index(
        "ix_monitoring_predictions_risk_level",
        "predictions",
        ["risk_level"],
        unique=False,
        schema="monitoring",
    )

    op.create_table(
        "dashboard_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("region_id", sa.BigInteger(), nullable=True),
        sa.Column("sla_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("avg_latency_ms", sa.Numeric(10, 2), nullable=False),
        sa.Column("congestion_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("active_alerts_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("anomalies_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_sessions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("sla_percent >= 0 AND sla_percent <= 100", name="ck_dashboard_sla_percent_range"),
        sa.CheckConstraint(
            "congestion_rate >= 0 AND congestion_rate <= 100",
            name="ck_dashboard_congestion_rate_range",
        ),
        sa.CheckConstraint("active_alerts_count >= 0", name="ck_dashboard_active_alerts_positive"),
        sa.CheckConstraint("anomalies_count >= 0", name="ck_dashboard_anomalies_positive"),
        sa.CheckConstraint("total_sessions >= 0", name="ck_dashboard_total_sessions_positive"),
        sa.ForeignKeyConstraint(
            ["region_id"],
            ["network.regions.id"],
            name="fk_dashboard_snapshots_region_id",
            ondelete="SET NULL",
        ),
        schema="dashboard",
    )
    op.create_index(
        "ix_dashboard_snapshots_region_generated_at",
        "dashboard_snapshots",
        ["region_id", "generated_at"],
        unique=False,
        schema="dashboard",
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index("ix_dashboard_snapshots_region_generated_at", table_name="dashboard_snapshots", schema="dashboard")
    op.drop_table("dashboard_snapshots", schema="dashboard")

    op.drop_index("ix_monitoring_predictions_risk_level", table_name="predictions", schema="monitoring")
    op.drop_index(
        "ix_monitoring_predictions_session_predicted_at",
        table_name="predictions",
        schema="monitoring",
    )
    op.drop_table("predictions", schema="monitoring")

    op.drop_index("ix_network_sessions_region_timestamp", table_name="sessions", schema="network")
    op.drop_index("ix_network_sessions_slice_type", table_name="sessions", schema="network")
    op.drop_index("ix_network_sessions_region_id", table_name="sessions", schema="network")
    op.drop_table("sessions", schema="network")

    op.drop_table("regions", schema="network")

    op.drop_index("ix_auth_users_is_active", table_name="users", schema="auth")
    op.drop_index("ix_auth_users_role", table_name="users", schema="auth")
    op.drop_table("users", schema="auth")

    risk_level_enum.drop(bind, checkfirst=True)
    slice_type_enum.drop(bind, checkfirst=True)
    ric_status_enum.drop(bind, checkfirst=True)
    user_role_enum.drop(bind, checkfirst=True)

    op.execute("DROP SCHEMA IF EXISTS dashboard")
    op.execute("DROP SCHEMA IF EXISTS monitoring")
    op.execute("DROP SCHEMA IF EXISTS network")
    op.execute("DROP SCHEMA IF EXISTS auth")
