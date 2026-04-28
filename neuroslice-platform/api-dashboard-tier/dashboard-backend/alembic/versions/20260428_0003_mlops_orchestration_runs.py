from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260428_0003"
down_revision = "20260427_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mlops_orchestration_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("action_key", sa.String(length=64), nullable=False),
        sa.Column("command_label", sa.String(length=255), nullable=False),
        sa.Column(
            "parameters_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "triggered_by_user_id",
            sa.BigInteger(),
            sa.ForeignKey("auth.users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("triggered_by_email", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("stdout_log", sa.Text(), nullable=True),
        sa.Column("stderr_log", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema="dashboard",
    )
    op.create_index(
        "ix_dashboard_mlops_orchestration_runs_status_started",
        "mlops_orchestration_runs",
        ["status", "started_at"],
        schema="dashboard",
    )
    op.create_index(
        "ix_dashboard_mlops_orchestration_runs_action",
        "mlops_orchestration_runs",
        ["action_key"],
        schema="dashboard",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dashboard_mlops_orchestration_runs_action",
        table_name="mlops_orchestration_runs",
        schema="dashboard",
    )
    op.drop_index(
        "ix_dashboard_mlops_orchestration_runs_status_started",
        table_name="mlops_orchestration_runs",
        schema="dashboard",
    )
    op.drop_table("mlops_orchestration_runs", schema="dashboard")
