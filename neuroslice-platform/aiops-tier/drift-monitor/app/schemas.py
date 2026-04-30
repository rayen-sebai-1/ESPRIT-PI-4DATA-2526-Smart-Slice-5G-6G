"""Pydantic schemas for drift events and state."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DriftState(BaseModel):
    """Latest drift detection state for one model. Stored in Redis as aiops:drift:{model_name}."""

    model_name: str
    # Possible statuses:
    # initializing | no_data | insufficient_data | reference_missing
    # alibi_unavailable | feature_count_mismatch | no_drift | drift_detected | error
    status: str = "no_data"
    deployment_version: str = "unknown"
    window_size: int = 0
    window_capacity: int = 500
    reference_sample_count: int = 0
    reference_loaded: bool = False
    p_value: Optional[float] = None
    threshold: float = 0.01
    is_drift: bool = False
    drift_score: Optional[float] = None
    feature_names: List[str] = []
    severity: str = "NONE"
    recommendation: str = ""
    last_checked_at: Optional[str] = None
    last_drift_at: Optional[str] = None
    auto_trigger_enabled: bool = False
    scenario_b_live_mode: bool = True
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class DriftEvent(BaseModel):
    """Drift alert event published to Redis stream events.drift and Kafka drift.alert."""

    event_type: str = "drift.detected"
    drift_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_name: str
    deployment_version: str = "unknown"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    window_size: int = 500
    reference_sample_count: int = 0
    p_value: float = 1.0
    threshold: float = 0.01
    is_drift: bool = True
    drift_score: Optional[float] = None
    feature_names: List[str] = []
    top_shifted_features: List[str] = []
    severity: str = "MEDIUM"
    recommendation: str = ""
    auto_trigger_enabled: bool = False
    scenario_b_live_mode: bool = True
