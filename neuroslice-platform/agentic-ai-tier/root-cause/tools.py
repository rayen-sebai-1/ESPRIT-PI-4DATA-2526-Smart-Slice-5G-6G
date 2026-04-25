from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _parse_time_range(time_range: str) -> Dict[str, str]:
    default_range = {"start": "-30m", "stop": "now()"}
    if not time_range:
        return default_range

    try:
        parsed = json.loads(time_range)
        if isinstance(parsed, dict) and "start" in parsed and "stop" in parsed:
            start = str(parsed["start"]).strip() or default_range["start"]
            stop = str(parsed["stop"]).strip() or default_range["stop"]
            return {"start": start, "stop": stop}
    except json.JSONDecodeError:
        logger.warning("Could not decode time_range JSON. Falling back to default range.")

    return default_range


def _build_timestamps(points: int) -> List[str]:
    now_utc = datetime.now(timezone.utc)
    return [
        (now_utc - timedelta(minutes=(points - idx - 1) * 3)).isoformat().replace("+00:00", "Z")
        for idx in range(points)
    ]


def fetch_influx_kpis_raw(slice_id: str, time_range: str) -> Dict[str, Any]:
    normalized_slice_id = (slice_id or "").strip()
    if not normalized_slice_id:
        raise ValueError("slice_id is required for fetch_influx_kpis")

    if normalized_slice_id.lower().startswith("simulate-tool-failure"):
        raise RuntimeError("Simulated Influx tool failure requested by slice_id pattern")

    normalized_range = _parse_time_range(time_range)
    timestamps = _build_timestamps(points=12)

    packet_loss = [0.4, 0.6, 0.9, 1.4, 2.2, 3.1, 4.7, 5.3, 5.0, 4.6, 3.9, 3.2]
    rb_util = [58.0, 62.0, 68.0, 73.0, 80.0, 87.0, 93.0, 96.0, 94.0, 91.0, 88.0, 84.0]
    latency = [11.2, 12.8, 13.7, 15.9, 18.4, 21.8, 26.4, 28.1, 27.0, 24.7, 22.0, 19.8]
    congestion_score = [0.24, 0.29, 0.33, 0.42, 0.56, 0.68, 0.82, 0.91, 0.87, 0.80, 0.72, 0.65]
    health_score = [0.94, 0.93, 0.91, 0.88, 0.82, 0.75, 0.64, 0.57, 0.61, 0.66, 0.71, 0.76]

    # flux_query = f"""
    # // Influx client configuration:
    # // org: neuroslice
    # // bucket: telemetry
    #
    # telemetry_data = from(bucket: "telemetry")
    #   |> range(start: {normalized_range["start"]}, stop: {normalized_range["stop"]})
    #   |> filter(fn: (r) => r._measurement == "telemetry")
    #   |> filter(fn: (r) => r.slice_id == "{normalized_slice_id}")
    #   |> filter(fn: (r) => r.domain == "core" or r.domain == "edge" or r.domain == "ran")
    #   |> filter(fn: (r) =>
    #       r._field == "kpi_packetLossPct" or
    #       r._field == "kpi_rbUtilizationPct" or
    #       r._field == "kpi_forwardingLatencyMs" or
    #       r._field == "derived_congestionScore" or
    #       r._field == "derived_healthScore" or
    #       r._field == "derived_misroutingScore" or
    #       r._field == "severity"
    #   )
    #
    # faults_data = from(bucket: "telemetry")
    #   |> range(start: {normalized_range["start"]}, stop: {normalized_range["stop"]})
    #   |> filter(fn: (r) => r._measurement == "faults")
    #   |> filter(fn: (r) => r.type == "aggregate" or r.type == "fault")
    #   |> filter(fn: (r) =>
    #       r._field == "active_count" or
    #       r._field == "severity" or
    #       r._field == "active"
    #   )
    #   |> filter(fn: (r) => exists r.affected_entities and r.affected_entities =~ /{normalized_slice_id}/)
    #
    # union(tables: [telemetry_data, faults_data])
    # """

    return {
        "org": "neuroslice",
        "bucket": "telemetry",
        "slice_id": normalized_slice_id,
        "time_range": normalized_range,
        "telemetry": {
            "measurement": "telemetry",
            "tags": {
                "domain": "ran",
                "entity_id": "cell-07",
                "entity_type": "cell",
                "slice_id": normalized_slice_id,
                "slice_type": "URLLC",
            },
            "timestamps": timestamps,
            "kpi_packetLossPct": packet_loss,
            "kpi_rbUtilizationPct": rb_util,
            "kpi_forwardingLatencyMs": latency,
            "derived_congestionScore": congestion_score,
            "derived_healthScore": health_score,
            "derived_misroutingScore": [0.09, 0.08, 0.11, 0.12, 0.16, 0.19, 0.20, 0.22, 0.20, 0.17, 0.15, 0.13],
            "severity": [1, 1, 1, 2, 2, 3, 4, 4, 4, 3, 3, 2],
        },
        "faults": {
            "measurement": "faults",
            "records": [
                {
                    "type": "fault",
                    "fault_id": "flt-ran-8421",
                    "fault_type": "ran_congestion",
                    "scenario_id": "scenario-ran-overload",
                    "affected_entities": "gnb-01,cell-07",
                    "active_count": 1,
                    "severity": 4,
                    "active": 1,
                },
                {
                    "type": "aggregate",
                    "fault_id": "flt-slice-5530",
                    "fault_type": "packet_loss_spike",
                    "scenario_id": "scenario-ran-overload",
                    "affected_entities": "slice:" + normalized_slice_id,
                    "active_count": 2,
                    "severity": 3,
                    "active": 1,
                },
            ],
        },
        "aiops_context": {
            "aiops_congestion": {
                "service": "congestion-detector",
                "entity_id": "cell-07",
                "entity_type": "cell",
                "site_id": "TT-SFAX-02",
                "slice_id": normalized_slice_id,
                "latest_score": 0.91,
            },
            "aiops_slice_classification": {
                "service": "slice-classifier",
                "entity_id": "cell-07",
                "entity_type": "cell",
                "site_id": "TT-SFAX-02",
                "slice_id": normalized_slice_id,
                "predicted_slice_type": "URLLC",
                "confidence": 0.96,
            },
            "aiops_sla": {
                "service": "sla-assurance",
                "entity_id": "cell-07",
                "entity_type": "cell",
                "site_id": "TT-SFAX-02",
                "slice_id": normalized_slice_id,
                "sla_risk_score": 0.84,
                "sla_breach_risk": True,
            },
        },
    }


def fetch_redis_state_raw(slice_id: str) -> Dict[str, Any]:
    normalized_slice_id = (slice_id or "").strip()
    if not normalized_slice_id:
        raise ValueError("slice_id is required for fetch_redis_state")

    if normalized_slice_id.lower().startswith("simulate-tool-failure"):
        raise RuntimeError("Simulated Redis tool failure requested by slice_id pattern")

    return {
        "key": f"slice:{normalized_slice_id}:state",
        "slice_id": normalized_slice_id,
        "domain": "ran",
        "slice_type": "URLLC",
        "site_id": "TT-SFAX-02",
        "status": "degraded",
        "active_entities": ["gnb-01", "cell-07", "edge-upf-01"],
        "entity_states": {
            "gnb-01": {"entity_type": "gnb", "health": "degraded"},
            "cell-07": {"entity_type": "cell", "health": "critical"},
            "edge-upf-01": {"entity_type": "edge_upf", "health": "warning"},
        },
        "fault_flags": {
            "ran_congestion": True,
            "packet_loss_spike": True,
            "telemetry_drop": False,
            "slice_misrouting": False,
        },
        "latest_scores": {
            "derived_congestionScore": 0.91,
            "derived_healthScore": 0.57,
            "derived_misroutingScore": 0.22,
            "severity": 4,
        },
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


@tool
def fetch_influx_kpis(slice_id: str, time_range: str) -> Dict[str, Any]:
    """
    Fetches telemetry/fault context for a slice from InfluxDB.
    This implementation is mocked for local RCA agent development.
    """
    try:
        return fetch_influx_kpis_raw(slice_id=slice_id, time_range=time_range)
    except Exception as exc:
        logger.exception("fetch_influx_kpis failed: %s", exc)
        raise RuntimeError(f"fetch_influx_kpis failed: {exc}") from exc


@tool
def fetch_redis_state(slice_id: str) -> Dict[str, Any]:
    """
    Fetches the current live state hash for a slice from Redis.
    This implementation is mocked for local RCA agent development.
    """
    try:
        return fetch_redis_state_raw(slice_id=slice_id)
    except Exception as exc:
        logger.exception("fetch_redis_state failed: %s", exc)
        raise RuntimeError(f"fetch_redis_state failed: {exc}") from exc
