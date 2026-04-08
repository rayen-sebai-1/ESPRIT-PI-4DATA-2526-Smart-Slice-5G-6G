from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from packages.neuroslice_common.enums import RICStatus


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
    ric_status: RICStatus
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


class ManagerSummaryResponse(BaseModel):
    national_overview: NationalOverview
    regions_comparison: list[RegionComparison]
    sla_trend: list[TrendPoint]
    congestion_trend: list[TrendPoint]
