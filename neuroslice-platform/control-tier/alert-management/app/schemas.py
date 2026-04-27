"""Pydantic schemas for Alert Management."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AlertType(str, Enum):
    CONGESTION = "CONGESTION"
    SLA_RISK = "SLA_RISK"
    SLICE_MISMATCH = "SLICE_MISMATCH"
    FAULT_EVENT = "FAULT_EVENT"
    UNKNOWN = "UNKNOWN"


class AlertSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class Alert(BaseModel):
    alert_id: str = Field(default_factory=lambda: str(uuid4()))
    dedup_key: str
    entity_id: str
    slice_id: str | None = None
    domain: str | None = None
    alert_type: AlertType
    severity: AlertSeverity
    source: str
    status: AlertStatus = AlertStatus.OPEN
    summary: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    event_count: int = 1
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
