from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

UserRole = Literal["ADMIN", "NETWORK_OPERATOR", "NETWORK_MANAGER", "DATA_MLOPS_ENGINEER"]
AssignableRole = Literal["NETWORK_OPERATOR", "NETWORK_MANAGER", "DATA_MLOPS_ENGINEER"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
RicStatus = Literal["HEALTHY", "DEGRADED", "CRITICAL", "MAINTENANCE"]
SliceType = Literal["eMBB", "URLLC", "mMTC", "ERLLC", "feMBB", "umMTC", "MBRLLC", "mURLLC"]


class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    role: UserRole
    is_active: bool


class LoginPayload(BaseModel):
    email: str
    password: str


class AdminCreateUserPayload(BaseModel):
    full_name: str
    email: str
    password: str = Field(min_length=6)
    role: AssignableRole = "NETWORK_OPERATOR"


class AdminUpdateUserPayload(BaseModel):
    full_name: str | None = None
    role: AssignableRole | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=6)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class RegionSummary(BaseModel):
    id: int
    code: str
    name: str
    ric_status: RicStatus
    network_load: float
    gnodeb_count: int


class PredictionSummary(BaseModel):
    id: int
    sla_score: float
    congestion_score: float
    anomaly_score: float
    risk_level: RiskLevel
    predicted_slice_type: SliceType
    slice_confidence: float
    recommended_action: str
    model_source: str
    predicted_at: datetime


class SessionSummary(BaseModel):
    id: int
    session_code: str
    region: RegionSummary
    slice_type: SliceType
    latency_ms: float
    packet_loss: float
    throughput_mbps: float
    timestamp: datetime
    prediction: PredictionSummary | None = None


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class SessionListResponse(BaseModel):
    items: list[SessionSummary]
    pagination: PaginationMeta


class RegionLite(BaseModel):
    id: int
    code: str
    name: str
    ric_status: RicStatus
    network_load: float


class PredictionResponse(BaseModel):
    id: int
    session_id: int
    session_code: str
    region: RegionLite
    sla_score: float
    congestion_score: float
    anomaly_score: float
    risk_level: RiskLevel
    predicted_slice_type: SliceType
    slice_confidence: float
    recommended_action: str
    model_source: str
    predicted_at: datetime


class PredictionListResponse(BaseModel):
    items: list[PredictionResponse]
    pagination: PaginationMeta


class ModelInfo(BaseModel):
    name: str
    purpose: str
    implementation: str
    status: str
    source_notebook: str
    artifact_path: str | None


class RunBatchRequest(BaseModel):
    region_id: int | None = None
    limit: int = Field(default=10, ge=1, le=50)


class NationalOverview(BaseModel):
    sla_national_percent: float
    avg_latency_ms: float
    congestion_rate: float
    active_alerts_count: int
    sessions_count: int
    anomalies_count: int
    generated_at: datetime | None


class RegionComparison(BaseModel):
    region_id: int
    code: str
    name: str
    ric_status: RicStatus
    network_load: float
    gnodeb_count: int
    sessions_count: int
    sla_percent: float
    avg_latency_ms: float
    avg_packet_loss: float
    congestion_rate: float
    high_risk_sessions_count: int
    anomalies_count: int


class TrendPoint(BaseModel):
    label: str
    generated_at: datetime
    sla_percent: float
    congestion_rate: float
    active_alerts_count: int
    anomalies_count: int
    total_sessions: int


class SliceDistributionPoint(BaseModel):
    slice_type: str
    sessions_count: int


class NationalDashboardResponse(BaseModel):
    overview: NationalOverview
    regions: list[RegionComparison]


class RegionDashboardResponse(BaseModel):
    region: RegionComparison
    gnodeb_count: int
    packet_loss_avg: float
    slice_distribution: list[SliceDistributionPoint]
    trend: list[TrendPoint]
