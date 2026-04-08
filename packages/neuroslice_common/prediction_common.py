from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from packages.neuroslice_common.enums import RiskLevel, SliceType
from packages.neuroslice_common.models import NetworkSession, Region

SLA_FEATURES = (
    "Packet Loss Rate",
    "Packet delay",
    "Smart City & Home",
    "IoT Devices",
    "Public Safety",
)

SLICE_FEATURES = (
    "LTE/5g Category",
    "Packet Loss Rate",
    "Packet delay",
    "Smartphone",
    "IoT Devices",
    "GBR",
)

CONGESTION_FEATURES = (
    "cpu_util_pct",
    "mem_util_pct",
    "bw_util_pct",
    "active_users",
    "queue_len",
    "hour",
    "slice_type_encoded",
)

ANOMALY_FEATURES = (
    "latency_gap_ns",
    "jitter_gap_ns",
    "packet_loss_gap",
    "data_rate_gap_gbps",
    "latency_ratio",
    "jitter_ratio",
    "packet_loss_ratio",
    "data_rate_ratio",
    "violation_count",
    "weighted_violation_score",
    "severity_score",
    "required_mobility_flag",
    "required_connectivity_flag",
    "slice_handover_flag",
    "slice_mismatch",
)

CONGESTION_SLICE_ALIASES = {
    "eMBB": "feMBB",
    "URLLC": "mURLLC",
    "mMTC": "umMTC",
}

ANOMALY_SLICE_ALIASES = {
    "eMBB": "feMBB",
    "URLLC": "mURLLC",
    "mMTC": "umMTC",
}

SLICE_CLASS_TO_RUNTIME = {
    "eMBB": SliceType.EMBB,
    "mMTC": SliceType.MMTC,
    "URLLC": SliceType.URLLC,
    "1": SliceType.EMBB,
    "2": SliceType.MMTC,
    "3": SliceType.URLLC,
}

RUNTIME_SLICE_TO_CLASS = {
    SliceType.EMBB.value: "eMBB",
    SliceType.FEMBB.value: "eMBB",
    SliceType.MBRLLC.value: "eMBB",
    SliceType.MMTC.value: "mMTC",
    SliceType.UMMTC.value: "mMTC",
    SliceType.URLLC.value: "URLLC",
    SliceType.ERLLC.value: "URLLC",
    SliceType.MURLLC.value: "URLLC",
}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def decimal_to_float(value: float | Decimal | None) -> float:
    return float(value) if value is not None else 0.0


def normalize_packet_loss(packet_loss: float) -> float:
    normalized = packet_loss / 100.0 if packet_loss > 0.05 else packet_loss
    return clamp(normalized, 0.0, 0.02)


def normalize_packet_delay(packet_delay: float, divisor: float = 1.0) -> float:
    if divisor <= 0:
        divisor = 1.0
    return clamp(packet_delay / divisor, 0.0, 300.0)


def normalize_slice_class(value: str | SliceType) -> str:
    key = value.value if isinstance(value, SliceType) else str(value)
    return RUNTIME_SLICE_TO_CLASS.get(key, key)


def compute_risk_level(sla_score: float, congestion_score: float, anomaly_score: float) -> RiskLevel:
    composite_risk = max(1.0 - sla_score, congestion_score, anomaly_score)
    if composite_risk >= 0.85:
        return RiskLevel.CRITICAL
    if composite_risk >= 0.65:
        return RiskLevel.HIGH
    if composite_risk >= 0.40:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def normalize_decision_score(raw_score: float, min_score: float, max_score: float) -> float:
    if max_score <= min_score:
        return 0.5
    return clamp((raw_score - min_score) / (max_score - min_score), 0.0, 1.0)


@dataclass(slots=True)
class PredictionResult:
    sla_score: float
    congestion_score: float
    anomaly_score: float
    risk_level: RiskLevel
    predicted_slice_type: SliceType
    slice_confidence: float
    recommended_action: str
    model_source: str


@dataclass(slots=True)
class ModelDescriptor:
    name: str
    purpose: str
    implementation: str
    status: str
    source_notebook: str
    artifact_path: str | None


@dataclass(slots=True)
class AnomalyEvaluation:
    anomaly_score: float
    misrouting_flag: bool
    expected_slice_type: str | None
    violation_count: int
    severity_score: float


class PredictionProvider(Protocol):
    def predict(self, session: NetworkSession, region: Region) -> PredictionResult:
        ...

    def catalog(self) -> list[ModelDescriptor]:
        ...
