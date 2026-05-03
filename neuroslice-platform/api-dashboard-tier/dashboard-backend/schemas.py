from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

UserRole = Literal["ADMIN", "NETWORK_OPERATOR", "NETWORK_MANAGER", "DATA_MLOPS_ENGINEER"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
RicStatus = Literal["HEALTHY", "DEGRADED", "CRITICAL", "MAINTENANCE"]
SliceType = Literal["eMBB", "URLLC", "mMTC", "ERLLC", "feMBB", "umMTC", "MBRLLC", "mURLLC"]


class AuthenticatedPrincipal(BaseModel):
    id: int
    session_id: str
    full_name: str
    email: str
    role: UserRole
    is_active: bool


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


class DashboardPreferencesPayload(BaseModel):
    preferences: dict[str, Any] = Field(default_factory=dict)


class DashboardPreferencesResponse(BaseModel):
    scope: str
    preferences: dict[str, Any]
    updated_at: datetime | None


class DashboardBookmarkPayload(BaseModel):
    resource_key: str
    resource_type: str
    title: str
    payload: dict[str, Any] = Field(default_factory=dict)


class DashboardBookmarkResponse(BaseModel):
    id: int
    resource_key: str
    resource_type: str
    title: str
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AlertAcknowledgePayload(BaseModel):
    note: str | None = None


class AlertAcknowledgementResponse(BaseModel):
    id: int
    alert_key: str
    note: str | None
    acknowledged_at: datetime


class MlopsModelMetrics(BaseModel):
    val_accuracy: float | None = None
    val_precision: float | None = None
    val_recall: float | None = None
    val_f1: float | None = None
    val_roc_auc: float | None = None


class MlopsPromotedModel(BaseModel):
    deployment_name: str
    model_name: str | None = None
    version: str | None = None
    framework: str | None = None
    run_id: str | None = None
    updated_at: str | None = None
    created_at: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    artifact_available: bool = False
    artifact_files: list[str] = Field(default_factory=list)


class MlopsRegistryEntry(BaseModel):
    model_name: str
    version: int | str | None = None
    stage: str | None = None
    promoted: bool = False
    framework: str | None = None
    model_family: str | None = None
    quality_gate_status: str | None = None
    promotion_status: str | None = None
    onnx_export_status: str | None = None
    created_at: str | None = None
    run_id: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    reason: str | None = None


class MlopsModelHealth(BaseModel):
    deployment_name: str
    promoted: MlopsPromotedModel | None = None
    registry: MlopsRegistryEntry | None = None
    health: Literal["healthy", "degraded", "unknown"] = "unknown"
    notes: list[str] = Field(default_factory=list)


class MlopsRunSummary(BaseModel):
    model_name: str
    version: int | str | None = None
    run_id: str | None = None
    stage: str | None = None
    quality_gate_status: str | None = None
    promotion_status: str | None = None
    created_at: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)


class MlopsArtifactStatus(BaseModel):
    deployment_name: str
    has_metadata: bool
    has_onnx: bool
    has_onnx_fp16: bool
    files: list[str] = Field(default_factory=list)


class MlopsPromotionEvent(BaseModel):
    model_name: str
    version: int | str | None = None
    run_id: str | None = None
    stage: str | None = None
    promotion_status: str | None = None
    promoted: bool = False
    reason: str | None = None
    created_at: str | None = None


class MlopsOverview(BaseModel):
    generated_at: str | None
    registry_available: bool
    promoted_models_count: int
    models_with_pass_gate: int
    models_with_fail_gate: int
    pending_runs: int
    promoted_models: list[MlopsModelHealth]
    sources: dict[str, str]


class MlopsPredictionMonitoringPoint(BaseModel):
    timestamp: str
    model: str | None = None
    region: str | None = None
    risk_level: str | None = None
    sla_score: float | None = None


class MlopsPredictionMonitoringResponse(BaseModel):
    available: bool
    source: str
    total: int
    items: list[MlopsPredictionMonitoringPoint] = Field(default_factory=list)
    note: str | None = None


class MlopsPromoteRequest(BaseModel):
    model_name: str
    version: int | str | None = None
    run_id: str | None = None


class MlopsRollbackRequest(BaseModel):
    model_name: str
    target_version: int | str | None = None


class MlopsActionResponse(BaseModel):
    accepted: bool
    action: str
    model_name: str
    detail: str
    delegated_to: str | None = None


PipelineRunStatus = Literal["QUEUED", "RUNNING", "SUCCESS", "FAILED", "TIMEOUT", "DISABLED", "CANCELLED"]


class MlopsToolLink(BaseModel):
    key: str
    name: str
    url: str
    description: str


class MlopsToolsResponse(BaseModel):
    tools: list[MlopsToolLink]


class MlopsToolHealth(BaseModel):
    name: str
    url: str
    status: Literal["UP", "DOWN", "UNKNOWN"]
    latency_ms: int | None = None
    detail: str | None = None


class MlopsToolsHealthResponse(BaseModel):
    services: list[MlopsToolHealth]


class MlopsPipelineRunResponse(BaseModel):
    run_id: str
    triggered_by_user_id: int | None
    triggered_by_email: str | None
    status: PipelineRunStatus
    command_label: str
    started_at: datetime | None
    finished_at: datetime | None
    exit_code: int | None
    duration_seconds: float | None
    created_at: datetime


class MlopsPipelineRunLogsResponse(BaseModel):
    run_id: str
    status: PipelineRunStatus
    stdout: str
    stderr: str


class MlopsActionDefinition(BaseModel):
    action_key: str
    label: str
    description: str
    risk_level: RiskLevel
    requires_confirmation: bool
    allowed_roles: list[UserRole]


class MlopsOrchestrationRunRequest(BaseModel):
    action: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class MlopsOrchestrationRunResponse(BaseModel):
    run_id: str
    action_key: str
    command_label: str
    parameters: dict[str, Any]
    triggered_by_user_id: int | None
    triggered_by_email: str | None
    trigger_source: str = "manual"
    status: PipelineRunStatus
    started_at: datetime | None
    finished_at: datetime | None
    exit_code: int | None
    duration_seconds: float | None
    created_at: datetime


class MlopsOrchestrationRunLogsResponse(BaseModel):
    run_id: str
    status: PipelineRunStatus
    stdout: str
    stderr: str


class MlopsPipelineConfigResponse(BaseModel):
    pipeline_enabled: bool
    message: str


MlopsRetrainingRequestStatus = Literal[
    "pending_approval",
    "approved",
    "rejected",
    "running",
    "completed",
    "failed",
    "skipped",
]

MlopsRetrainingTriggerType = Literal["DRIFT", "SCHEDULED", "MANUAL"]
MlopsRetrainingScheduleFrequency = Literal["DAILY", "WEEKLY", "MONTHLY", "CUSTOM_CRON"]
MlopsRetrainingScheduleStatus = Literal["ACTIVE", "DISABLED", "ERROR"]


class MlopsRetrainingRequest(BaseModel):
    id: str
    model: str
    model_internal: str | None = None
    pipeline_action: str | None = None
    trigger_type: MlopsRetrainingTriggerType | None = None
    reason: str
    anomaly_count: int
    threshold: int
    severity: str | None = None
    drift_score: float | None = None
    p_value: float | None = None
    request_source: str | None = None
    source_schedule_id: str | None = None
    status: MlopsRetrainingRequestStatus
    created_at: str
    approved_by: str | None = None
    approved_at: str | None = None
    executed_by: str | None = None
    executed_at: str | None = None
    completed_at: str | None = None
    updated_at: str | None = None
    execution_run_id: str | None = None
    execution_detail: str | None = None


class MlopsRetrainingRequestListResponse(BaseModel):
    count: int
    items: list[MlopsRetrainingRequest]


class MlopsRetrainingScheduleBase(BaseModel):
    model_name: str = Field(min_length=1, max_length=128)
    enabled: bool = True
    frequency: MlopsRetrainingScheduleFrequency
    cron_expr: str = Field(min_length=1, max_length=128)
    timezone: str = Field(min_length=1, max_length=64)
    require_approval: bool = True


class MlopsRetrainingScheduleCreate(MlopsRetrainingScheduleBase):
    allow_duplicate_enabled: bool = False


class MlopsRetrainingScheduleUpdate(BaseModel):
    model_name: str | None = Field(default=None, min_length=1, max_length=128)
    enabled: bool | None = None
    frequency: MlopsRetrainingScheduleFrequency | None = None
    cron_expr: str | None = Field(default=None, min_length=1, max_length=128)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    require_approval: bool | None = None
    allow_duplicate_enabled: bool = False


class MlopsRetrainingScheduleResponse(BaseModel):
    id: str
    model_name: str
    enabled: bool
    frequency: MlopsRetrainingScheduleFrequency
    cron_expr: str
    timezone: str
    require_approval: bool
    created_by: str
    created_at: datetime
    updated_at: datetime
    last_run_at: datetime | None
    next_run_at: datetime | None
    status: MlopsRetrainingScheduleStatus


class MlopsRetrainingScheduleListResponse(BaseModel):
    count: int
    items: list[MlopsRetrainingScheduleResponse]


class AgenticHealthResponse(BaseModel):
    root_cause: str
    copilot: str
    detail: dict[str, Any] = Field(default_factory=dict)
