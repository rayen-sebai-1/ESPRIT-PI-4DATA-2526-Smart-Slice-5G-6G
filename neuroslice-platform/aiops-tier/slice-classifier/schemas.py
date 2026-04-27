"""Pydantic schemas for slice-classifier."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class CanonicalTelemetryEvent(BaseModel):
    event_id: str = Field(alias="eventId")
    timestamp: str
    domain: str
    site_id: Optional[str] = Field(default=None, alias="siteId")
    node_id: Optional[str] = Field(default=None, alias="nodeId")
    entity_id: str = Field(alias="entityId")
    entity_type: str = Field(alias="entityType")
    slice_id: Optional[str] = Field(default=None, alias="sliceId")
    slice_type: Optional[str] = Field(default=None, alias="sliceType")
    kpis: Dict[str, Any] = {}
    derived: Dict[str, Any] = {}
    scenario_id: Optional[str] = Field(default="normal_day", alias="scenarioId")

    class Config:
        populate_by_name = True


class SliceClassificationEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="eventId")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    service: str
    site_id: str = Field(alias="siteId")
    slice_id: Optional[str] = Field(default=None, alias="sliceId")
    entity_id: str = Field(alias="entityId")
    entity_type: str = Field(alias="entityType")
    severity: int
    score: float
    prediction: str
    model_version: str = Field(alias="modelVersion")
    source_event_id: str = Field(alias="sourceEventId")
    source_stream: str = Field(default="stream:norm.telemetry", alias="sourceStream")
    domain: str = "unknown"
    explanation: Optional[str] = None
    details: Dict[str, Any] = {}

    class Config:
        populate_by_name = True
