"""Feature extraction from normalized telemetry events for drift detection.

Feature vectors must stay in sync with the AIOps worker inference.py files.
Reference: aiops-tier/{congestion-detector,sla-assurance,slice-classifier}/inference.py
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Canonical encoding must match the fallback in congestion-detector/inference.py
SLICE_TYPE_ENCODING = {"eMBB": 0, "URLLC": 1, "mMTC": 2}

# Stable feature schemas — source of truth for drift_feature_schema.json
FEATURE_SCHEMAS: Dict[str, Dict] = {
    "congestion_5g": {
        "feature_names": [
            "cpu_util_pct",
            "mem_util_pct",
            "bw_util_pct",
            "active_users",
            "queue_len",
            "hour",
            "slice_type_encoded",
        ],
        "feature_count": 7,
        "drift_method": "alibi_detect_mmd",
        "p_value_threshold": 0.01,
        "window_size": 500,
    },
    "sla_5g": {
        "feature_names": [
            "packet_loss_pct",
            "packet_delay_ms",
            "smart_city_home",
            "iot_devices",
            "public_safety",
        ],
        "feature_count": 5,
        "drift_method": "alibi_detect_mmd",
        "p_value_threshold": 0.01,
        "window_size": 500,
    },
    "slice_type_5g": {
        "feature_names": [
            "lte5g_category",
            "packet_loss_pct",
            "packet_delay_ms",
            "smartphone",
            "iot_devices",
            "gbr",
        ],
        "feature_count": 6,
        "drift_method": "alibi_detect_mmd",
        "p_value_threshold": 0.01,
        "window_size": 500,
    },
}


def extract_features(event: Dict[str, Any], model_name: str) -> Optional[List[float]]:
    """Extract a feature vector from a normalized telemetry event for the given model."""
    try:
        if model_name == "congestion_5g":
            return _extract_congestion_features(event)
        if model_name == "sla_5g":
            return _extract_sla_features(event)
        if model_name == "slice_type_5g":
            return _extract_slice_type_features(event)
        logger.warning("Unknown model_name for feature extraction: %s", model_name)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.debug("Feature extraction failed for %s: %s", model_name, exc)
        return None


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _event_hour(timestamp: Optional[str]) -> int:
    if not timestamp:
        return datetime.utcnow().hour
    try:
        ts = timestamp.replace("Z", "+00:00")
        return datetime.fromisoformat(ts).hour
    except Exception:  # noqa: BLE001
        return datetime.utcnow().hour


def _extract_congestion_features(event: Dict[str, Any]) -> List[float]:
    """7 features matching congestion-detector/inference.py CongestionInferencer._feature_row."""
    kpis = event.get("kpis") or {}
    derived = event.get("derived") or {}

    cpu = _as_float(
        kpis.get("cpuUtilPct"),
        default=_as_float(derived.get("congestionScore")) * 100.0,
    )
    mem = _as_float(kpis.get("memUtilPct"), default=cpu * 0.8)
    bw = _as_float(
        kpis.get("rbUtilizationPct"),
        default=_as_float(
            kpis.get("queueDepthPct"),
            default=_as_float(derived.get("congestionScore")) * 100.0,
        ),
    )
    active_users = _as_float(
        kpis.get("ueCount"),
        default=_as_float(
            kpis.get("activeUeCount"),
            default=_as_float(kpis.get("activeSessions")),
        ),
    )
    queue_len = _as_float(
        kpis.get("registrationQueueLen"),
        default=_as_float(
            kpis.get("pduSetupQueueLen"),
            default=_as_float(kpis.get("queueDepthPct")),
        ),
    )
    hour = float(_event_hour(event.get("timestamp")))
    slice_type = event.get("sliceType") or ""
    slice_type_encoded = float(SLICE_TYPE_ENCODING.get(slice_type, -1))

    return [cpu, mem, bw, active_users, queue_len, hour, slice_type_encoded]


def _extract_sla_features(event: Dict[str, Any]) -> List[float]:
    """5 features matching sla-assurance/inference.py SlaInferencer._feature_vector."""
    kpis = event.get("kpis") or {}

    packet_loss = _as_float(kpis.get("packetLossPct"))
    packet_delay = _as_float(
        kpis.get("latencyMs"),
        default=_as_float(kpis.get("forwardingLatencyMs"), default=20.0),
    )

    observed = (event.get("sliceType") or "").lower()
    smart_city_home = 1.0 if observed == "mmtc" else 0.0
    iot_devices = 1.0 if observed == "mmtc" else 0.0
    public_safety = 1.0 if observed == "urllc" else 0.0

    return [packet_loss, packet_delay, smart_city_home, iot_devices, public_safety]


def _extract_slice_type_features(event: Dict[str, Any]) -> List[float]:
    """6 features matching slice-classifier/inference.py SliceInferencer._feature_vector."""
    kpis = event.get("kpis") or {}
    derived = event.get("derived") or {}

    lte5g_category = 2.0  # 5G NR always
    packet_loss = _as_float(
        kpis.get("packetLossPct"),
        default=_as_float(derived.get("congestionScore")) * 2.0,
    )
    packet_delay = _as_float(
        kpis.get("latencyMs"),
        default=_as_float(kpis.get("forwardingLatencyMs"), default=15.0),
    )

    throughput = _as_float(
        kpis.get("dlThroughputMbps"),
        default=_as_float(kpis.get("throughputMbps")),
    )
    ue_count = _as_float(
        kpis.get("ueCount"),
        default=_as_float(kpis.get("activeUeCount")),
    )

    observed = (event.get("sliceType") or "").lower()
    smartphone = 1.0 if observed == "embb" or throughput >= 150.0 else 0.0
    iot_devices = 1.0 if observed == "mmtc" or ue_count >= 250.0 else 0.0
    gbr = 1.0 if observed in {"embb", "urllc"} or packet_delay < 25.0 else 0.0

    return [lte5g_category, packet_loss, packet_delay, smartphone, iot_devices, gbr]
