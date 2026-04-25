from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

VALID_DOMAINS = {"core", "edge", "ran"}
VALID_ENTITY_TYPES = {"amf", "smf", "upf", "edge_upf", "mec_app", "compute_node", "gnb", "cell"}
VALID_SLICE_TYPES = {"eMBB", "URLLC", "mMTC"}


def _build_timestamps(points: int = 8) -> List[str]:
    now_utc = datetime.now(timezone.utc)
    return [
        (now_utc - timedelta(minutes=(points - index - 1) * 2)).isoformat().replace("+00:00", "Z")
        for index in range(points)
    ]


def _normalize_query_parameters(query_parameters: Any) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    if isinstance(query_parameters, dict):
        for key, value in query_parameters.items():
            normalized[str(key)] = str(value).strip()
    return normalized


def _extract_slice_id(
    slice_id: Optional[str],
    query_parameters: Optional[Dict[str, Any]],
) -> str:
    direct_value = (slice_id or "").strip()
    if direct_value:
        return direct_value

    params = _normalize_query_parameters(query_parameters or {})
    nested = params.get("slice_id", "").strip()
    if nested:
        return nested

    # Keep tools robust when the model sends incomplete argument objects.
    return "slice-001"


@tool
def fetch_influx_kpis(query_parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Mocked InfluxDB query for the canonical NeuroSlice contract:
    org=neuroslice, bucket=telemetry, measurements telemetry/faults.
    """
    try:
        params = _normalize_query_parameters(query_parameters or {})

        slice_id = params.get("slice_id", "slice-001") or "slice-001"
        domain = params.get("domain", "ran").lower()
        entity_type = params.get("entity_type", "cell")
        slice_type = params.get("slice_type", "URLLC")
        entity_id = params.get("entity_id", f"{entity_type}-01") or f"{entity_type}-01"

        if domain not in VALID_DOMAINS:
            domain = "ran"
        if entity_type not in VALID_ENTITY_TYPES:
            entity_type = "cell"
        if slice_type not in VALID_SLICE_TYPES:
            slice_type = "URLLC"

        timestamps = _build_timestamps(points=10)
        telemetry_records: List[Dict[str, Any]] = []
        for idx, ts in enumerate(timestamps):
            telemetry_records.append(
                {
                    "timestamp": ts,
                    "measurement": "telemetry",
                    "tags": {
                        "domain": domain,
                        "entity_id": entity_id,
                        "entity_type": entity_type,
                        "slice_id": slice_id,
                        "slice_type": slice_type,
                    },
                    "fields": {
                        "kpi_cpuUtilPct": round(52.0 + idx * 3.1, 2),
                        "kpi_packetLossPct": round(0.6 + idx * 0.42, 2),
                        "kpi_rbUtilizationPct": round(61.0 + idx * 2.8, 2),
                        "derived_congestionScore": round(0.32 + idx * 0.05, 4),
                        "derived_healthScore": round(0.93 - idx * 0.04, 4),
                    },
                }
            )

        faults_records = [
            {
                "timestamp": timestamps[-2],
                "measurement": "faults",
                "tags": {
                    "type": "fault",
                    "fault_id": "flt-ran-3249",
                    "fault_type": "ran_congestion",
                },
                "fields": {"active_count": 1, "severity": 4, "active": 1},
            },
            {
                "timestamp": timestamps[-1],
                "measurement": "faults",
                "tags": {
                    "type": "aggregate",
                    "fault_id": "flt-slice-9011",
                    "fault_type": "packet_loss_spike",
                },
                "fields": {"active_count": 2, "severity": 3, "active": 1},
            },
        ]

        return {
            "org": "neuroslice",
            "bucket": "telemetry",
            "query_parameters": {
                "domain": domain,
                "entity_type": entity_type,
                "slice_id": slice_id,
                "slice_type": slice_type,
                "entity_id": entity_id,
            },
            "telemetry": telemetry_records,
            "faults": faults_records,
        }
    except Exception as exc:
        logger.exception("fetch_influx_kpis failed: %s", exc)
        raise RuntimeError(f"fetch_influx_kpis failed: {exc}") from exc


@tool
def fetch_redis_state(
    slice_id: str = "",
    query_parameters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Mocked Redis hash lookup for live slice state.
    """
    try:
        normalized_slice_id = _extract_slice_id(slice_id=slice_id, query_parameters=query_parameters)
        if not normalized_slice_id:
            raise ValueError("slice_id is required")

        now_ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return {
            "redis_key": f"slice:{normalized_slice_id}:state",
            "slice_id": normalized_slice_id,
            "status": "degraded",
            "state_hash": {
                "domain": "ran",
                "slice_type": "URLLC",
                "priority": "high",
                "active_faults": ["ran_congestion", "packet_loss_spike"],
                "active_entities": ["gnb-17", "cell-17A", "edge_upf-04"],
                "latest_scores": {
                    "derived_congestionScore": 0.87,
                    "derived_healthScore": 0.58,
                },
                "updated_at": now_ts,
            },
        }
    except Exception as exc:
        logger.exception("fetch_redis_state failed: %s", exc)
        raise RuntimeError(f"fetch_redis_state failed: {exc}") from exc
