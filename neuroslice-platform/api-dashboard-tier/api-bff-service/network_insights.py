"""
network_insights.py

Influx-backed read API powering the National and Regional dashboards.

Concepts:
- "Region" in this product = network functional domain: core | edge | ran.
  These are real Influx tags on `telemetry`, and entity_type maps deterministically
  to a domain for `faults` / `aiops_*` measurements where the tag is absent.
- "Network logs" = derived events (fault open/close, KPI breach, AIOps prediction,
  slice mismatch) computed from the same Influx data. Each event has a uniform shape.

This module owns:
- InfluxClient (one shared singleton)
- All Flux query construction
- The folding of raw points into the canonical event DTO
- Cheap in-process result cache (2s TTL)

It exposes only `national_overview()`, `region_overview(domain)`, and `network_logs(...)`.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from influxdb_client import InfluxDBClient
except Exception:  # pragma: no cover - dependency is optional in unit envs
    InfluxDBClient = None  # type: ignore

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Constants & taxonomy
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_WINDOW = "-15m"
ALLOWED_WINDOWS = {"-5m", "-15m", "-1h", "-6h", "-24h"}

# Functional-domain regions surfaced by the dashboard.
REGIONS: List[Dict[str, Any]] = [
    {
        "id": "core",
        "code": "CORE",
        "name": "Core network",
        "description": "AMF, SMF and core UPF functions.",
    },
    {
        "id": "edge",
        "code": "EDGE",
        "name": "Edge & MEC",
        "description": "Edge UPF, MEC apps and compute nodes.",
    },
    {
        "id": "ran",
        "code": "RAN",
        "name": "Radio access (RAN)",
        "description": "gNodeBs and cells serving end users.",
    },
]
REGION_IDS = {item["id"] for item in REGIONS}

# entity_type -> functional domain. Used to scope faults / AIOps measurements
# that don't carry a domain tag in Influx.
ENTITY_TYPE_TO_DOMAIN: Dict[str, str] = {
    "amf": "core", "smf": "core", "upf": "core",
    "edge_upf": "edge", "mec_app": "edge", "compute_node": "edge",
    "gnb": "ran", "cell": "ran",
}

KPI_BREACH_RULES: List[Dict[str, Any]] = [
    {"field": "derived_healthScore", "op": "lt", "threshold": 0.6,
     "category": "KPI_HEALTH", "severity": 2,
     "message_fmt": "Health score collapsed to {value:.2f} on {entity_id}"},
    {"field": "derived_congestionScore", "op": "gt", "threshold": 0.8,
     "category": "KPI_CONGESTION", "severity": 2,
     "message_fmt": "Congestion score {value:.2f} on {entity_id}"},
    {"field": "kpi_packetLossPct", "op": "gt", "threshold": 1.0,
     "category": "KPI_PACKET_LOSS", "severity": 1,
     "message_fmt": "Packet loss {value:.2f}% on {entity_id}"},
    {"field": "kpi_rbUtilizationPct", "op": "gt", "threshold": 90.0,
     "category": "KPI_RB_UTIL", "severity": 1,
     "message_fmt": "RB utilization {value:.0f}% on {entity_id}"},
    {"field": "kpi_forwardingLatencyMs", "op": "gt", "threshold": 30.0,
     "category": "KPI_LATENCY", "severity": 1,
     "message_fmt": "Forwarding latency {value:.1f}ms on {entity_id}"},
]

LOG_CATEGORIES = {
    "FAULT_OPENED", "FAULT_CLEARED",
    "AIOPS_CONGESTION", "AIOPS_SLA", "AIOPS_SLICE_MISMATCH",
    "KPI_HEALTH", "KPI_CONGESTION", "KPI_PACKET_LOSS",
    "KPI_RB_UTIL", "KPI_LATENCY",
}


def normalize_window(window: Optional[str]) -> str:
    if window and window in ALLOWED_WINDOWS:
        return window
    return DEFAULT_WINDOW


def normalize_region(region_id: Optional[str]) -> Optional[str]:
    if not region_id:
        return None
    candidate = str(region_id).strip().lower()
    return candidate if candidate in REGION_IDS else None


def derive_domain(entity_id: Optional[str], entity_type: Optional[str]) -> Optional[str]:
    if entity_type:
        mapped = ENTITY_TYPE_TO_DOMAIN.get(entity_type)
        if mapped:
            return mapped
    if entity_id:
        eid = str(entity_id).lower()
        if eid.startswith("slice-embb") or eid.startswith("slice-urllc") or eid.startswith("slice-mmtc"):
            return "ran"
        prefix = eid.split("-", 1)[0]
        for et, dom in ENTITY_TYPE_TO_DOMAIN.items():
            if prefix == et or eid.startswith(et):
                return dom
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Influx client + tiny TTL cache
# ─────────────────────────────────────────────────────────────────────────────

class InfluxClient:
    def __init__(self) -> None:
        self.url = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
        self.token = os.getenv("INFLUXDB_TOKEN", "neuroslice_token_12345")
        self.org = os.getenv("INFLUXDB_ORG", "neuroslice")
        self.bucket = os.getenv("INFLUXDB_BUCKET", "telemetry")
        self.timeout_ms = int(os.getenv("INFLUXDB_TIMEOUT_MS", "8000"))

    def query(self, flux: str) -> List[Any]:
        if InfluxDBClient is None:
            raise RuntimeError("influxdb-client is not installed")
        client = InfluxDBClient(url=self.url, token=self.token, org=self.org, timeout=self.timeout_ms)
        try:
            return list(client.query_api().query(org=self.org, query=flux))
        finally:
            client.close()


_cache_lock = threading.Lock()
_cache: Dict[str, Tuple[float, Any]] = {}
CACHE_TTL_SECONDS = 2.0


def _cached(key: str, build) -> Any:
    now = time.monotonic()
    with _cache_lock:
        entry = _cache.get(key)
        if entry and now - entry[0] < CACHE_TTL_SECONDS:
            return entry[1]
    value = build()
    with _cache_lock:
        _cache[key] = (now, value)
    return value


# ─────────────────────────────────────────────────────────────────────────────
# Flux helpers
# ─────────────────────────────────────────────────────────────────────────────

def _flux_escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _records(tables: Iterable[Any]) -> Iterable[Any]:
    for table in tables:
        for record in getattr(table, "records", []):
            yield record


def _record_values(record: Any) -> Dict[str, Any]:
    return getattr(record, "values", {}) or {}


def _record_time(record: Any) -> Optional[datetime]:
    try:
        return record.get_time()
    except Exception:
        return None


def _to_iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> Optional[int]:
    f = _coerce_float(value)
    return int(f) if f is not None else None


# ─────────────────────────────────────────────────────────────────────────────
# Telemetry aggregation (KPIs + per-domain breakdown)
# ─────────────────────────────────────────────────────────────────────────────

TELEMETRY_KPI_FIELDS = (
    "derived_healthScore",
    "derived_congestionScore",
    "kpi_packetLossPct",
    "kpi_rbUtilizationPct",
    "kpi_forwardingLatencyMs",
    "kpi_latencyMs",
    "kpi_dlThroughputMbps",
    "kpi_ueCount",
    "kpi_activeSessions",
    "kpi_cpuUtilPct",
    "kpi_memUtilPct",
)


def _build_telemetry_flux(
    bucket: str, window: str, domain: Optional[str], fields: Sequence[str]
) -> str:
    field_filter = " or ".join(f'r._field == "{_flux_escape(f)}"' for f in fields)
    domain_filter = ""
    if domain:
        domain_filter = f'  |> filter(fn: (r) => r.domain == "{_flux_escape(domain)}")\n'
    return (
        f'from(bucket: "{_flux_escape(bucket)}")\n'
        f"  |> range(start: {window})\n"
        f'  |> filter(fn: (r) => r._measurement == "telemetry")\n'
        f"  |> filter(fn: (r) => {field_filter})\n"
        f"{domain_filter}"
        f"  |> last()\n"
    )


def fetch_telemetry_aggregate(window: str, domain: Optional[str]) -> Dict[str, Any]:
    """Latest value per (entity_id, domain, field). Returns aggregates ready for KPI cards."""
    flux = _build_telemetry_flux(InfluxClient().bucket, window, domain, TELEMETRY_KPI_FIELDS)
    tables = InfluxClient().query(flux)

    by_field: Dict[str, List[float]] = defaultdict(list)
    by_domain_field: Dict[Tuple[str, str], List[float]] = defaultdict(list)
    entities_by_domain: Dict[str, set] = defaultdict(set)
    slices_by_domain: Dict[str, set] = defaultdict(set)
    slice_type_counts: Dict[str, int] = defaultdict(int)
    breaches: int = 0

    for record in _records(tables):
        values = _record_values(record)
        field = record.get_field()
        raw_value = _coerce_float(record.get_value())
        if raw_value is None:
            continue
        rec_domain = (values.get("domain") or "").strip()
        entity_id = (values.get("entity_id") or "").strip()
        slice_id = (values.get("slice_id") or "").strip()
        slice_type = (values.get("slice_type") or "").strip()

        by_field[field].append(raw_value)
        if rec_domain:
            by_domain_field[(rec_domain, field)].append(raw_value)
            if entity_id:
                entities_by_domain[rec_domain].add(entity_id)
            if slice_id and slice_id.lower() != "none":
                slices_by_domain[rec_domain].add(slice_id)
        if slice_type and slice_type.lower() != "none":
            slice_type_counts[slice_type] += 1

        for rule in KPI_BREACH_RULES:
            if rule["field"] != field:
                continue
            if rule["op"] == "lt" and raw_value < rule["threshold"]:
                breaches += 1
            elif rule["op"] == "gt" and raw_value > rule["threshold"]:
                breaches += 1

    def _avg(values: List[float]) -> Optional[float]:
        return sum(values) / len(values) if values else None

    def _max(values: List[float]) -> Optional[float]:
        return max(values) if values else None

    health_avg = _avg(by_field.get("derived_healthScore", []))
    congestion_avg = _avg(by_field.get("derived_congestionScore", []))
    packet_loss_avg = _avg(by_field.get("kpi_packetLossPct", []))
    rb_util_avg = _avg(by_field.get("kpi_rbUtilizationPct", []))
    latency_avg = _avg(by_field.get("kpi_forwardingLatencyMs", [])) or _avg(
        by_field.get("kpi_latencyMs", [])
    )
    throughput_total = sum(by_field.get("kpi_dlThroughputMbps", []) or [])
    ue_total = sum(by_field.get("kpi_ueCount", []) or [])
    sessions_total = sum(by_field.get("kpi_activeSessions", []) or [])

    domain_breakdown: List[Dict[str, Any]] = []
    domains_seen = sorted({d for d, _ in by_domain_field.keys()})
    for d in domains_seen:
        domain_breakdown.append({
            "domain": d,
            "entities_count": len(entities_by_domain.get(d, set())),
            "slices_count": len(slices_by_domain.get(d, set())),
            "health_avg": _avg(by_domain_field.get((d, "derived_healthScore"), [])),
            "congestion_avg": _avg(by_domain_field.get((d, "derived_congestionScore"), [])),
            "packet_loss_avg": _avg(by_domain_field.get((d, "kpi_packetLossPct"), [])),
            "rb_util_avg": _avg(by_domain_field.get((d, "kpi_rbUtilizationPct"), [])),
            "latency_avg": _avg(by_domain_field.get((d, "kpi_forwardingLatencyMs"), []))
                            or _avg(by_domain_field.get((d, "kpi_latencyMs"), [])),
            "throughput_total": sum(by_domain_field.get((d, "kpi_dlThroughputMbps"), []) or []),
            "ue_total": sum(by_domain_field.get((d, "kpi_ueCount"), []) or []),
            "sessions_total": sum(by_domain_field.get((d, "kpi_activeSessions"), []) or []),
        })

    slice_distribution = sorted(
        ({"slice_type": k, "entities_count": v} for k, v in slice_type_counts.items()),
        key=lambda item: item["entities_count"],
        reverse=True,
    )

    return {
        "kpis": {
            "health_avg": health_avg,
            "congestion_avg": congestion_avg,
            "packet_loss_avg": packet_loss_avg,
            "rb_util_avg": rb_util_avg,
            "latency_avg": latency_avg,
            "throughput_total_mbps": throughput_total,
            "ue_total": ue_total,
            "sessions_total": sessions_total,
            "kpi_breach_count": breaches,
        },
        "entities_count": sum(len(s) for s in entities_by_domain.values()),
        "slices_count": sum(len(s) for s in slices_by_domain.values()),
        "domain_breakdown": domain_breakdown,
        "slice_distribution": slice_distribution,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Trend (downsampled time series)
# ─────────────────────────────────────────────────────────────────────────────

WINDOW_TO_AGGREGATE_EVERY = {
    "-5m": "30s",
    "-15m": "1m",
    "-1h": "5m",
    "-6h": "15m",
    "-24h": "1h",
}


def _build_trend_flux(bucket: str, window: str, domain: Optional[str]) -> str:
    every = WINDOW_TO_AGGREGATE_EVERY.get(window, "1m")
    domain_filter = ""
    if domain:
        domain_filter = f'  |> filter(fn: (r) => r.domain == "{_flux_escape(domain)}")\n'
    return (
        f'from(bucket: "{_flux_escape(bucket)}")\n'
        f"  |> range(start: {window})\n"
        f'  |> filter(fn: (r) => r._measurement == "telemetry")\n'
        f'  |> filter(fn: (r) => r._field == "derived_healthScore" or r._field == "derived_congestionScore" or r._field == "kpi_packetLossPct")\n'
        f"{domain_filter}"
        f"  |> aggregateWindow(every: {every}, fn: mean, createEmpty: false)\n"
        f'  |> keep(columns: ["_time", "_field", "_value"])\n'
        f'  |> group(columns: ["_field"])\n'
        f"  |> sort(columns: [\"_time\"])\n"
    )


def fetch_trend(window: str, domain: Optional[str]) -> List[Dict[str, Any]]:
    flux = _build_trend_flux(InfluxClient().bucket, window, domain)
    tables = InfluxClient().query(flux)
    bucketed: Dict[str, Dict[str, Any]] = {}
    for record in _records(tables):
        ts = _to_iso(_record_time(record))
        if not ts:
            continue
        field = record.get_field()
        value = _coerce_float(record.get_value())
        if value is None:
            continue
        slot = bucketed.setdefault(ts, {"timestamp": ts})
        if field == "derived_healthScore":
            slot["health"] = value
            slot["sla_percent"] = max(0.0, min(100.0, value * 100))
        elif field == "derived_congestionScore":
            slot["congestion"] = value
            slot["congestion_rate"] = max(0.0, min(100.0, value * 100))
        elif field == "kpi_packetLossPct":
            slot["packet_loss_pct"] = value
    return sorted(bucketed.values(), key=lambda item: item["timestamp"])


# ─────────────────────────────────────────────────────────────────────────────
# Faults
# ─────────────────────────────────────────────────────────────────────────────

def _build_faults_flux(bucket: str, window: str) -> str:
    return (
        f'from(bucket: "{_flux_escape(bucket)}")\n'
        f"  |> range(start: {window})\n"
        f'  |> filter(fn: (r) => r._measurement == "faults")\n'
        f'  |> filter(fn: (r) => r._field == "active" or r._field == "active_count" or r._field == "severity")\n'
    )


def fetch_faults_events(window: str) -> List[Dict[str, Any]]:
    flux = _build_faults_flux(InfluxClient().bucket, window)
    tables = InfluxClient().query(flux)
    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for record in _records(tables):
        values = _record_values(record)
        fault_id = values.get("fault_id") or "unknown"
        ts_iso = _to_iso(_record_time(record))
        key = (str(fault_id), ts_iso or "")
        slot = grouped.setdefault(key, {
            "fault_id": fault_id,
            "fault_type": values.get("fault_type"),
            "scenario_id": values.get("scenario_id"),
            "site_id": values.get("site_id"),
            "type": values.get("type"),
            "affected_entities": _split_entities(values.get("affected_entities")),
            "ts": ts_iso,
        })
        field = record.get_field()
        if field == "active":
            slot["active"] = bool(_coerce_int(record.get_value()))
        elif field == "active_count":
            slot["active_count"] = _coerce_int(record.get_value())
        elif field == "severity":
            slot["severity"] = _coerce_int(record.get_value()) or 0

    events: List[Dict[str, Any]] = []
    # We emit one event per (fault_id, ts) row; aggregator rows (type=aggregate) are skipped.
    for slot in grouped.values():
        if (slot.get("type") or "").lower() == "aggregate":
            continue
        affected = slot.get("affected_entities", [])
        domain = None
        for entity in affected:
            if entity.startswith("slice:"):
                continue
            domain = derive_domain(entity, None)
            if domain:
                break
        category = "FAULT_OPENED" if slot.get("active") else "FAULT_CLEARED"
        primary_entity = next((e for e in affected if not e.startswith("slice:")), None)
        slice_id = next(
            (e.split(":", 1)[1] for e in affected if e.startswith("slice:")),
            None,
        )
        message = "{type} fault {state} on {target}".format(
            type=slot.get("fault_type") or "unknown",
            state="opened" if slot.get("active") else "cleared",
            target=primary_entity or slice_id or "network",
        )
        events.append({
            "id": f"FAULT:{slot['fault_id']}:{slot['ts']}",
            "ts": slot["ts"],
            "category": category,
            "severity": slot.get("severity") or 1,
            "domain": domain,
            "slice_id": slice_id,
            "entity_id": primary_entity,
            "entity_type": None,
            "slice_type": None,
            "message": message,
            "evidence": {
                "fault_id": slot["fault_id"],
                "fault_type": slot.get("fault_type"),
                "scenario_id": slot.get("scenario_id"),
                "active_count": slot.get("active_count"),
                "affected_entities": affected,
            },
        })
    return events


def _split_entities(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[,;]\s*", value) if item.strip()]
    return [str(value)]


# ─────────────────────────────────────────────────────────────────────────────
# AIOps events
# ─────────────────────────────────────────────────────────────────────────────

AIOPS_MEASUREMENTS = {
    "aiops_congestion": {"category": "AIOPS_CONGESTION", "alert_pred": "congestion_anomaly"},
    "aiops_sla": {"category": "AIOPS_SLA", "alert_pred": "sla_at_risk"},
    "aiops_slice_classification": {"category": "AIOPS_SLICE_MISMATCH", "alert_pred": None},
}


def _build_aiops_flux(bucket: str, measurement: str, window: str) -> str:
    return (
        f'from(bucket: "{_flux_escape(bucket)}")\n'
        f"  |> range(start: {window})\n"
        f'  |> filter(fn: (r) => r._measurement == "{_flux_escape(measurement)}")\n'
        f'  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")\n'
    )


def fetch_aiops_events(window: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    bucket = InfluxClient().bucket
    for measurement, meta in AIOPS_MEASUREMENTS.items():
        try:
            tables = InfluxClient().query(_build_aiops_flux(bucket, measurement, window))
        except Exception as exc:
            logger.warning("aiops fetch failed for %s: %s", measurement, exc)
            continue
        category = meta["category"]
        alert_pred = meta["alert_pred"]
        for record in _records(tables):
            values = _record_values(record)
            prediction = values.get("prediction")
            severity = _coerce_int(values.get("severity")) or 0
            score = _coerce_float(values.get("score")) or _coerce_float(values.get("risk_score")) or _coerce_float(values.get("confidence"))
            entity_id = values.get("entity_id")
            entity_type = values.get("entity_type")
            slice_id = values.get("slice_id")

            is_alert = severity >= 1 or (alert_pred and str(prediction) == alert_pred)
            if not is_alert:
                continue

            ts_iso = _to_iso(_record_time(record))
            domain = derive_domain(entity_id, entity_type)
            message = "{cat} prediction={pred} on {target}".format(
                cat=category.replace("AIOPS_", "").replace("_", " ").lower(),
                pred=prediction or "?",
                target=entity_id or slice_id or "?",
            )
            events.append({
                "id": f"{category}:{entity_id or slice_id}:{ts_iso}",
                "ts": ts_iso,
                "category": category,
                "severity": severity if severity > 0 else 1,
                "domain": domain,
                "slice_id": slice_id,
                "entity_id": entity_id,
                "entity_type": entity_type,
                "slice_type": None,
                "message": message,
                "evidence": {
                    "prediction": prediction,
                    "score": score,
                    "service": values.get("service"),
                    "site_id": values.get("site_id"),
                },
            })
    return events


# ─────────────────────────────────────────────────────────────────────────────
# KPI breach events (derived from telemetry)
# ─────────────────────────────────────────────────────────────────────────────

def _build_breach_flux(bucket: str, window: str, domain: Optional[str]) -> str:
    fields = sorted({rule["field"] for rule in KPI_BREACH_RULES})
    field_filter = " or ".join(f'r._field == "{_flux_escape(f)}"' for f in fields)
    domain_filter = ""
    if domain:
        domain_filter = f'  |> filter(fn: (r) => r.domain == "{_flux_escape(domain)}")\n'
    return (
        f'from(bucket: "{_flux_escape(bucket)}")\n'
        f"  |> range(start: {window})\n"
        f'  |> filter(fn: (r) => r._measurement == "telemetry")\n'
        f"  |> filter(fn: (r) => {field_filter})\n"
        f"{domain_filter}"
        f'  |> group(columns: ["entity_id","entity_type","domain","slice_id","slice_type","_field"])\n'
        f"  |> last()\n"
    )


def fetch_kpi_breach_events(window: str, domain: Optional[str]) -> List[Dict[str, Any]]:
    flux = _build_breach_flux(InfluxClient().bucket, window, domain)
    tables = InfluxClient().query(flux)
    events: List[Dict[str, Any]] = []
    rules_by_field = {rule["field"]: rule for rule in KPI_BREACH_RULES}
    for record in _records(tables):
        values = _record_values(record)
        field = record.get_field()
        rule = rules_by_field.get(field)
        if not rule:
            continue
        value = _coerce_float(record.get_value())
        if value is None:
            continue
        triggered = (rule["op"] == "lt" and value < rule["threshold"]) or (
            rule["op"] == "gt" and value > rule["threshold"]
        )
        if not triggered:
            continue
        ts_iso = _to_iso(_record_time(record))
        entity_id = values.get("entity_id")
        events.append({
            "id": f"{rule['category']}:{entity_id}:{ts_iso}",
            "ts": ts_iso,
            "category": rule["category"],
            "severity": rule["severity"],
            "domain": values.get("domain") or derive_domain(entity_id, values.get("entity_type")),
            "slice_id": values.get("slice_id"),
            "entity_id": entity_id,
            "entity_type": values.get("entity_type"),
            "slice_type": values.get("slice_type"),
            "message": rule["message_fmt"].format(value=value, entity_id=entity_id or "?"),
            "evidence": {
                "field": field,
                "value": value,
                "threshold": rule["threshold"],
                "operator": rule["op"],
            },
        })
    return events


# ─────────────────────────────────────────────────────────────────────────────
# Public composition: overview + logs
# ─────────────────────────────────────────────────────────────────────────────

def _faults_summary_for(window: str, domain: Optional[str]) -> Dict[str, Any]:
    fault_events = fetch_faults_events(window)
    if domain:
        fault_events = [e for e in fault_events if e.get("domain") == domain]
    active_open = [e for e in fault_events if e["category"] == "FAULT_OPENED"]
    return {
        "active_count": len(active_open),
        "events_count": len(fault_events),
    }


def _aiops_summary_for(window: str, domain: Optional[str]) -> Dict[str, int]:
    aiops_events = fetch_aiops_events(window)
    if domain:
        aiops_events = [e for e in aiops_events if e.get("domain") == domain]
    counts = {"AIOPS_CONGESTION": 0, "AIOPS_SLA": 0, "AIOPS_SLICE_MISMATCH": 0}
    for e in aiops_events:
        if e["category"] in counts:
            counts[e["category"]] += 1
    return counts


def national_overview(window: str = DEFAULT_WINDOW) -> Dict[str, Any]:
    window = normalize_window(window)
    cache_key = f"national::{window}"

    def build():
        agg = fetch_telemetry_aggregate(window, domain=None)
        faults = _faults_summary_for(window, domain=None)
        aiops = _aiops_summary_for(window, domain=None)
        trend = fetch_trend(window, domain=None)
        return {
            "generated_at": _to_iso(datetime.now(timezone.utc)),
            "window": window,
            "kpis": agg["kpis"],
            "entities_count": agg["entities_count"],
            "slices_count": agg["slices_count"],
            "active_faults_count": faults["active_count"],
            "fault_events_count": faults["events_count"],
            "aiops_counts": aiops,
            "regions": [
                {**region, **_region_summary_from_breakdown(region["id"], agg["domain_breakdown"], faults_in_region=faults_for_domain(window, region["id"]))}
                for region in REGIONS
            ],
            "slice_distribution": agg["slice_distribution"],
            "trend": trend,
        }

    return _cached(cache_key, build)


def _region_summary_from_breakdown(domain: str, breakdown: List[Dict[str, Any]], faults_in_region: int) -> Dict[str, Any]:
    match = next((b for b in breakdown if b["domain"] == domain), None)
    if not match:
        return {
            "entities_count": 0, "slices_count": 0,
            "health_avg": None, "congestion_avg": None,
            "packet_loss_avg": None, "rb_util_avg": None, "latency_avg": None,
            "throughput_total_mbps": 0.0, "ue_total": 0, "sessions_total": 0,
            "active_faults_count": faults_in_region,
        }
    return {
        "entities_count": match["entities_count"],
        "slices_count": match["slices_count"],
        "health_avg": match["health_avg"],
        "congestion_avg": match["congestion_avg"],
        "packet_loss_avg": match["packet_loss_avg"],
        "rb_util_avg": match["rb_util_avg"],
        "latency_avg": match["latency_avg"],
        "throughput_total_mbps": match["throughput_total"],
        "ue_total": match["ue_total"],
        "sessions_total": match["sessions_total"],
        "active_faults_count": faults_in_region,
    }


def faults_for_domain(window: str, domain: str) -> int:
    cache_key = f"faults_per_domain::{window}::{domain}"

    def build():
        events = fetch_faults_events(window)
        return sum(1 for e in events if e.get("domain") == domain and e["category"] == "FAULT_OPENED")
    return _cached(cache_key, build)


def region_overview(domain: str, window: str = DEFAULT_WINDOW) -> Dict[str, Any]:
    domain = normalize_region(domain) or "core"
    window = normalize_window(window)
    cache_key = f"region::{domain}::{window}"

    def build():
        agg = fetch_telemetry_aggregate(window, domain=domain)
        faults = _faults_summary_for(window, domain=domain)
        aiops = _aiops_summary_for(window, domain=domain)
        trend = fetch_trend(window, domain=domain)
        region_meta = next((r for r in REGIONS if r["id"] == domain), {"id": domain, "name": domain})
        return {
            "generated_at": _to_iso(datetime.now(timezone.utc)),
            "window": window,
            "region": region_meta,
            "kpis": agg["kpis"],
            "entities_count": agg["entities_count"],
            "slices_count": agg["slices_count"],
            "active_faults_count": faults["active_count"],
            "fault_events_count": faults["events_count"],
            "aiops_counts": aiops,
            "domain_breakdown": agg["domain_breakdown"],
            "slice_distribution": agg["slice_distribution"],
            "trend": trend,
        }

    return _cached(cache_key, build)


def network_logs(
    scope: str = "national",
    region_id: Optional[str] = None,
    window: str = DEFAULT_WINDOW,
    categories: Optional[Sequence[str]] = None,
    min_severity: int = 0,
    limit: int = 200,
) -> Dict[str, Any]:
    window = normalize_window(window)
    domain = normalize_region(region_id) if scope == "regional" else None
    cat_set = {c for c in (categories or []) if c in LOG_CATEGORIES}
    cache_key = f"logs::{scope}::{domain or '*'}::{window}::{','.join(sorted(cat_set))}::{min_severity}::{limit}"

    def build():
        events: List[Dict[str, Any]] = []
        events.extend(fetch_faults_events(window))
        events.extend(fetch_aiops_events(window))
        events.extend(fetch_kpi_breach_events(window, domain=domain))

        if domain:
            events = [e for e in events if e.get("domain") == domain]
        if cat_set:
            events = [e for e in events if e.get("category") in cat_set]
        if min_severity > 0:
            events = [e for e in events if (e.get("severity") or 0) >= min_severity]

        events = [e for e in events if e.get("ts")]
        events.sort(key=lambda item: item.get("ts", ""), reverse=True)
        truncated = events[: max(1, min(limit, 500))]

        return {
            "scope": scope,
            "region_id": domain,
            "window": window,
            "generated_at": _to_iso(datetime.now(timezone.utc)),
            "count": len(truncated),
            "total_matches": len(events),
            "events": truncated,
        }

    return _cached(cache_key, build)


def list_regions() -> List[Dict[str, Any]]:
    return [dict(item) for item in REGIONS]
