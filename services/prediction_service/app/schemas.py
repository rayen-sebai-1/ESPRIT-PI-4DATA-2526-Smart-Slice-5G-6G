from __future__ import annotations

from datetime import datetime
from math import ceil

from pydantic import BaseModel

from packages.neuroslice_common.enums import RiskLevel, RICStatus, SliceType


class RegionLite(BaseModel):
    id: int
    code: str
    name: str
    ric_status: RICStatus
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


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def from_values(cls, *, page: int, page_size: int, total: int) -> "PaginationMeta":
        total_pages = ceil(total / page_size) if total else 0
        return cls(page=page, page_size=page_size, total=total, total_pages=total_pages)


class PredictionListResponse(BaseModel):
    items: list[PredictionResponse]
    pagination: PaginationMeta


class RunBatchRequest(BaseModel):
    region_id: int | None = None
    limit: int = 20


class ModelInfoResponse(BaseModel):
    name: str
    purpose: str
    implementation: str
    status: str
    source_notebook: str
    artifact_path: str | None
