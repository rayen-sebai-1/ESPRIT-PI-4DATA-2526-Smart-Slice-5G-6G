from __future__ import annotations

from datetime import datetime
from math import ceil
from typing import Optional

from pydantic import BaseModel

from packages.neuroslice_common.enums import RICStatus, RiskLevel, SliceType


class RegionSummary(BaseModel):
    id: int
    code: str
    name: str
    ric_status: RICStatus
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
    prediction: Optional[PredictionSummary] = None


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def from_values(cls, *, page: int, page_size: int, total: int) -> "PaginationMeta":
        total_pages = ceil(total / page_size) if total else 0
        return cls(page=page, page_size=page_size, total=total, total_pages=total_pages)


class SessionListResponse(BaseModel):
    items: list[SessionSummary]
    pagination: PaginationMeta
