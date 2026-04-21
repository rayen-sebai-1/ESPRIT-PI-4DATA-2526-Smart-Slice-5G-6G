"""
shared/models.py
Pydantic models used across all neuroslice-sim services.
Defines the canonical event schema and supporting types.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class Domain(str, Enum):
    CORE = "core"
    EDGE = "edge"
    RAN = "ran"


class SliceType(str, Enum):
    EMBB = "eMBB"
    URLLC = "URLLC"
    MMTC = "mMTC"


class EntityType(str, Enum):
    AMF = "amf"
    SMF = "smf"
    UPF = "upf"
    EDGE_UPF = "edge_upf"
    MEC_APP = "mec_app"
    COMPUTE_NODE = "compute_node"
    GNB = "gnb"
    CELL = "cell"


class Protocol(str, Enum):
    VES = "ves"
    NETCONF = "netconf"
    INTERNAL = "internal"


class FaultType(str, Enum):
    RAN_CONGESTION = "ran_congestion"
    EDGE_OVERLOAD = "edge_overload"
    AMF_DEGRADATION = "amf_degradation"
    UPF_OVERLOAD = "upf_overload"
    PACKET_LOSS_SPIKE = "packet_loss_spike"
    LATENCY_SPIKE = "latency_spike"
    TELEMETRY_DROP = "telemetry_drop"
    MALFORMED_TELEMETRY = "malformed_telemetry"
    SLICE_MISROUTING = "slice_misrouting"


class Severity(int, Enum):
    OK = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


# ─────────────────────────────────────────────────────────────────────────────
# Sub-models
# ─────────────────────────────────────────────────────────────────────────────

class RoutingInfo(BaseModel):
    expected_upf: str = Field(..., alias="expectedUpf")
    actual_upf: str = Field(..., alias="actualUpf")
    qos_profile_expected: str = Field(..., alias="qosProfileExpected")
    qos_profile_actual: str = Field(..., alias="qosProfileActual")

    class Config:
        populate_by_name = True


class DerivedMetrics(BaseModel):
    congestion_score: float = Field(0.0, alias="congestionScore")
    health_score: float = Field(1.0, alias="healthScore")
    misrouting_score: float = Field(0.0, alias="misroutingScore")

    class Config:
        populate_by_name = True


class FaultRef(BaseModel):
    fault_id: str = Field(..., alias="faultId")
    fault_type: str = Field(..., alias="faultType")
    severity: int = 1

    class Config:
        populate_by_name = True


# ─────────────────────────────────────────────────────────────────────────────
# Canonical telemetry event
# ─────────────────────────────────────────────────────────────────────────────

class CanonicalEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="eventId")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        alias="timestamp",
    )
    domain: Domain
    site_id: str = Field(..., alias="siteId")
    node_id: str = Field(..., alias="nodeId")
    entity_id: str = Field(..., alias="entityId")
    entity_type: EntityType = Field(..., alias="entityType")
    slice_id: Optional[str] = Field(None, alias="sliceId")
    slice_type: Optional[SliceType] = Field(None, alias="sliceType")
    protocol: Protocol = Protocol.INTERNAL
    vendor: str = "simulated"
    kpis: Dict[str, float] = {}
    derived: DerivedMetrics = Field(default_factory=DerivedMetrics)
    routing: Optional[RoutingInfo] = None
    faults: List[FaultRef] = []
    scenario_id: str = Field("normal_day", alias="scenarioId")
    severity: Severity = Severity.OK

    class Config:
        populate_by_name = True
        use_enum_values = True


# ─────────────────────────────────────────────────────────────────────────────
# Fault / scenario models
# ─────────────────────────────────────────────────────────────────────────────

class FaultEvent(BaseModel):
    fault_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    fault_type: FaultType
    start_time: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    duration_sec: float = 300.0
    affected_entities: List[str] = []
    severity: Severity = Severity.MEDIUM
    kpi_impacts: Dict[str, float] = {}  # kpi_name → multiplier
    active: bool = True
    scenario_id: str = "manual"

    class Config:
        use_enum_values = True


class ScenarioDefinition(BaseModel):
    scenario_id: str
    description: str
    duration_sec: float
    faults: List[Dict[str, Any]] = []
    traffic_modifier: float = 1.0  # multiplier on base load
    notes: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Entity state snapshot (for quick API reads from Redis hash)
# ─────────────────────────────────────────────────────────────────────────────

class EntityState(BaseModel):
    entity_id: str
    entity_type: EntityType
    domain: Domain
    health_score: float = 1.0
    congestion_score: float = 0.0
    misrouting_score: float = 0.0
    kpis: Dict[str, float] = {}
    active_faults: List[str] = []
    last_updated: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    class Config:
        use_enum_values = True


# ─────────────────────────────────────────────────────────────────────────────
# Raw telemetry payloads from adapters
# ─────────────────────────────────────────────────────────────────────────────

class RawVesEvent(BaseModel):
    """Raw VES event as sent by simulator services to the VES adapter."""
    source: str
    domain: str
    entity_id: str
    entity_type: str
    site_id: str
    node_id: str
    slice_id: Optional[str] = None
    slice_type: Optional[str] = None
    timestamp: str
    kpis: Dict[str, float]
    internal: Dict[str, Any] = {}  # internal truth fields for debugging
    scenario_id: str = "normal_day"


class RawNetconfEvent(BaseModel):
    """Hierarchical NETCONF-style telemetry blob."""
    source: str
    managed_element: str
    timestamp: str
    data: Dict[str, Any]  # nested YANG-like structure
    schema_version: str = "1.0"
    scenario_id: str = "normal_day"
