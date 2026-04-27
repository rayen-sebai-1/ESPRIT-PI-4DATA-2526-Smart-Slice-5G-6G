"""Pydantic schemas for Policy Control."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ActionType(str, Enum):
    RECOMMEND_PCF_QOS_UPDATE = "RECOMMEND_PCF_QOS_UPDATE"
    RECOMMEND_REROUTE_SLICE = "RECOMMEND_REROUTE_SLICE"
    RECOMMEND_SCALE_EDGE_RESOURCE = "RECOMMEND_SCALE_EDGE_RESOURCE"
    RECOMMEND_INSPECT_SLICE_POLICY = "RECOMMEND_INSPECT_SLICE_POLICY"
    INVESTIGATE_CONTEXT = "INVESTIGATE_CONTEXT"
    NO_ACTION = "NO_ACTION"


class ActionMode(str, Enum):
    RECOMMENDATION = "RECOMMENDATION"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ActionStatus(str, Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED_SIMULATED = "EXECUTED_SIMULATED"
    FAILED = "FAILED"


class Action(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid4()))
    alert_id: str
    entity_id: str
    slice_id: str | None = None
    domain: str | None = None
    action_type: ActionType
    mode: ActionMode = ActionMode.RECOMMENDATION
    risk_level: RiskLevel
    requires_approval: bool
    status: ActionStatus
    reason: str
    policy_id: str
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class PolicyDecision(BaseModel):
    action_type: ActionType
    risk_level: RiskLevel
    requires_approval: bool
    status: ActionStatus
    reason: str
    policy_id: str
