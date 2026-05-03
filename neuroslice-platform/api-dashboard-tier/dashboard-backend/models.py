from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BIGINT, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

AUTH_SCHEMA = "auth"
DASHBOARD_SCHEMA = "dashboard"


class Base(DeclarativeBase):
    pass


class AuthReadBase(DeclarativeBase):
    pass


class DashboardPreference(Base):
    __tablename__ = "dashboard_preferences"
    __table_args__ = (
        Index("ix_dashboard_preferences_user_id_scope", "user_id", "scope", unique=True),
        {"schema": DASHBOARD_SCHEMA},
    )

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT,
        nullable=False,
    )
    scope: Mapped[str] = mapped_column(String(64), nullable=False, server_default=text("'me'"))
    preferences: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class DashboardBookmark(Base):
    __tablename__ = "dashboard_bookmarks"
    __table_args__ = (
        Index("ix_dashboard_bookmarks_user_resource_key", "user_id", "resource_key", unique=True),
        {"schema": DASHBOARD_SCHEMA},
    )

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT,
        nullable=False,
    )
    resource_key: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AlertAcknowledgement(Base):
    __tablename__ = "alert_acknowledgements"
    __table_args__ = (
        Index("ix_dashboard_alert_acknowledgements_alert_user", "alert_key", "user_id", unique=True),
        {"schema": DASHBOARD_SCHEMA},
    )

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT,
        nullable=False,
    )
    alert_key: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    acknowledged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class MlopsPipelineRun(Base):
    __tablename__ = "mlops_pipeline_runs"
    __table_args__ = (
        Index("ix_dashboard_mlops_pipeline_runs_status_started", "status", "started_at"),
        {"schema": DASHBOARD_SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    triggered_by_user_id: Mapped[int | None] = mapped_column(
        BIGINT,
        nullable=True,
    )
    triggered_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    command_label: Mapped[str] = mapped_column(String(255), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stdout_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class MlopsOrchestrationRun(Base):
    __tablename__ = "mlops_orchestration_runs"
    __table_args__ = (
        Index("ix_dashboard_mlops_orchestration_runs_status_started", "status", "started_at"),
        Index("ix_dashboard_mlops_orchestration_runs_action", "action_key"),
        {"schema": DASHBOARD_SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    action_key: Mapped[str] = mapped_column(String(64), nullable=False)
    command_label: Mapped[str] = mapped_column(String(255), nullable=False)
    parameters_json: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    triggered_by_user_id: Mapped[int | None] = mapped_column(
        BIGINT,
        nullable=True,
    )
    triggered_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trigger_source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'manual'"),
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Integer, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stdout_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class MlopsRetrainingSchedule(Base):
    __tablename__ = "mlops_retraining_schedules"
    __table_args__ = (
        Index("ix_dashboard_mlops_retraining_schedules_enabled_next", "enabled", "next_run_at"),
        Index("ix_dashboard_mlops_retraining_schedules_model", "model_name"),
        {"schema": DASHBOARD_SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    frequency: Mapped[str] = mapped_column(String(32), nullable=False)
    cron_expr: Mapped[str] = mapped_column(String(128), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default=text("'UTC'"))
    require_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'ACTIVE'"),
    )


class AuthRole(AuthReadBase):
    __tablename__ = "roles"
    __table_args__ = {"schema": AUTH_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)


class AuthUser(AuthReadBase):
    __tablename__ = "users"
    __table_args__ = {"schema": AUTH_SCHEMA}

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey(f"{AUTH_SCHEMA}.roles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    role: Mapped[AuthRole] = relationship()


class AuthUserSession(AuthReadBase):
    __tablename__ = "user_sessions"
    __table_args__ = {"schema": AUTH_SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BIGINT, ForeignKey(f"{AUTH_SCHEMA}.users.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[AuthUser] = relationship()
