from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.neuroslice_common.db import Base
from packages.neuroslice_common.enums import RICStatus, RiskLevel, SliceType, UserRole

SLICE_TYPE_ENUM = Enum(
    SliceType,
    name="slice_type",
    values_callable=lambda enum_cls: [item.value for item in enum_cls],
)


class TimestampMixin:
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


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class Region(Base, TimestampMixin):
    __tablename__ = "regions"
    __table_args__ = (
        CheckConstraint("network_load >= 0 AND network_load <= 100", name="ck_regions_network_load_range"),
        CheckConstraint("gnodeb_count >= 0", name="ck_regions_gnodeb_count_positive"),
        {"schema": "network"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ric_status: Mapped[RICStatus] = mapped_column(Enum(RICStatus, name="ric_status"), nullable=False)
    network_load: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    gnodeb_count: Mapped[int] = mapped_column(Integer, nullable=False)

    sessions: Mapped[list["NetworkSession"]] = relationship(back_populates="region")
    snapshots: Mapped[list["DashboardSnapshot"]] = relationship(back_populates="region")


class NetworkSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("latency_ms >= 0", name="ck_sessions_latency_positive"),
        CheckConstraint("packet_loss >= 0", name="ck_sessions_packet_loss_positive"),
        CheckConstraint("throughput_mbps >= 0", name="ck_sessions_throughput_positive"),
        CheckConstraint("use_case_type <> ''", name="ck_sessions_use_case_type_not_empty"),
        CheckConstraint("lte_5g_category >= 1 AND lte_5g_category <= 22", name="ck_sessions_lte_5g_category_range"),
        CheckConstraint("smartphone IN (0, 1)", name="ck_sessions_smartphone_binary"),
        CheckConstraint("gbr IN (0, 1)", name="ck_sessions_gbr_binary"),
        CheckConstraint("iot_devices IN (0, 1)", name="ck_sessions_iot_devices_binary"),
        CheckConstraint("public_safety IN (0, 1)", name="ck_sessions_public_safety_binary"),
        CheckConstraint("smart_city_home IN (0, 1)", name="ck_sessions_smart_city_home_binary"),
        CheckConstraint("cpu_util_pct >= 0 AND cpu_util_pct <= 100", name="ck_sessions_cpu_util_pct_range"),
        CheckConstraint("mem_util_pct >= 0 AND mem_util_pct <= 100", name="ck_sessions_mem_util_pct_range"),
        CheckConstraint("bw_util_pct >= 0 AND bw_util_pct <= 100", name="ck_sessions_bw_util_pct_range"),
        CheckConstraint("active_users >= 0", name="ck_sessions_active_users_positive"),
        CheckConstraint("queue_len >= 0", name="ck_sessions_queue_len_positive"),
        CheckConstraint("packet_loss_budget >= 0", name="ck_sessions_packet_loss_budget_positive"),
        CheckConstraint("latency_budget_ns >= 0", name="ck_sessions_latency_budget_positive"),
        CheckConstraint("jitter_budget_ns >= 0", name="ck_sessions_jitter_budget_positive"),
        CheckConstraint("data_rate_budget_gbps >= 0", name="ck_sessions_data_rate_budget_positive"),
        CheckConstraint(
            "slice_available_transfer_rate_gbps >= 0",
            name="ck_sessions_slice_available_transfer_rate_positive",
        ),
        CheckConstraint("slice_latency_ns >= 0", name="ck_sessions_slice_latency_positive"),
        CheckConstraint("slice_packet_loss >= 0", name="ck_sessions_slice_packet_loss_positive"),
        CheckConstraint("slice_jitter_ns >= 0", name="ck_sessions_slice_jitter_positive"),
        {"schema": "network"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    region_id: Mapped[int] = mapped_column(
        ForeignKey("network.regions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    slice_type: Mapped[SliceType] = mapped_column(SLICE_TYPE_ENUM, nullable=False, index=True)
    use_case_type: Mapped[str] = mapped_column(String(120), nullable=False, default="Smart City", server_default="Smart City")
    required_mobility: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    required_connectivity: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    slice_handover: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    lte_5g_category: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default="10")
    smartphone: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    gbr: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    latency_ms: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    packet_loss: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    throughput_mbps: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    iot_devices: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    public_safety: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    smart_city_home: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    cpu_util_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0, server_default="0")
    mem_util_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0, server_default="0")
    bw_util_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0, server_default="0")
    active_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    queue_len: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    packet_loss_budget: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, default=0, server_default="0")
    latency_budget_ns: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    jitter_budget_ns: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    data_rate_budget_gbps: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0, server_default="0")
    slice_available_transfer_rate_gbps: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
        default=0,
        server_default="0",
    )
    slice_latency_ns: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    slice_packet_loss: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, default=0, server_default="0")
    slice_jitter_ns: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    region: Mapped["Region"] = relationship(back_populates="sessions")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint("sla_score >= 0 AND sla_score <= 1", name="ck_predictions_sla_score_range"),
        CheckConstraint("congestion_score >= 0 AND congestion_score <= 1", name="ck_predictions_congestion_score_range"),
        CheckConstraint("anomaly_score >= 0 AND anomaly_score <= 1", name="ck_predictions_anomaly_score_range"),
        CheckConstraint(
            "slice_confidence >= 0 AND slice_confidence <= 1",
            name="ck_predictions_slice_confidence_range",
        ),
        {"schema": "monitoring"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("network.sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sla_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    congestion_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    anomaly_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel, name="risk_level"), nullable=False, index=True)
    predicted_slice_type: Mapped[SliceType] = mapped_column(SLICE_TYPE_ENUM, nullable=False)
    slice_confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    model_source: Mapped[str] = mapped_column(String(255), nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    session: Mapped["NetworkSession"] = relationship(back_populates="predictions")


class DashboardSnapshot(Base):
    __tablename__ = "dashboard_snapshots"
    __table_args__ = (
        CheckConstraint("sla_percent >= 0 AND sla_percent <= 100", name="ck_dashboard_sla_percent_range"),
        CheckConstraint(
            "congestion_rate >= 0 AND congestion_rate <= 100",
            name="ck_dashboard_congestion_rate_range",
        ),
        CheckConstraint("active_alerts_count >= 0", name="ck_dashboard_active_alerts_positive"),
        CheckConstraint("anomalies_count >= 0", name="ck_dashboard_anomalies_positive"),
        CheckConstraint("total_sessions >= 0", name="ck_dashboard_total_sessions_positive"),
        {"schema": "dashboard"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    region_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("network.regions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sla_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    avg_latency_ms: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    congestion_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    active_alerts_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    anomalies_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_sessions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    region: Mapped[Optional["Region"]] = relationship(back_populates="snapshots")

