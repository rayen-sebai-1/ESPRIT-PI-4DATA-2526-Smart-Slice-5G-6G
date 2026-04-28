"""Influx-backed network event log feed for the live dashboards.

These are operational network events derived from telemetry, fault and AIOps
measurements. They are not container logs and this module never exposes Influx
credentials beyond the BFF process.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from influxdb_client import InfluxDBClient
except Exception:  # pragma: no cover - optional in lightweight test envs
    InfluxDBClient = None  # type: ignore

logger = logging.getLogger(__name__)

ALLOWED_STARTS = {"-5m", "-15m", "-1h", "-6h", "-24h"}
DEFAULT_START = "-15m"

LOG_CATEGORIES = {
    "FAULT_OPENED",
    "FAULT_CLEARED",
    "KPI_BREACH",
    "AIOPS_CONGESTION",
    "AIOPS_SLA_RISK",
    "AIOPS_SLICE_MISMATCH",
}

ENTITY_TYPE_TO_DOMAIN = {
    "amf": "core",
    "smf": "core",
    "upf": "core",
    "edge_upf": "edge",
    "mec_app": "edge",
    "compute_node": "edge",
    "gnb": "ran",
    "cell": "ran",
}

# Dashboard-backend currently models numeric Tunisian regions, while live
# telemetry only carries site_id/domain tags. Keep this mapping deliberately
# small and real; add entries only when telemetry tags exist for that region.
REGION_SITE_IDS = {
    "4": {"TT-SFAX-02"},
    "sf": {"TT-SFAX-02"},
    "sfax": {"TT-SFAX-02"},
}

DOMAIN_REGION_IDS = {"core", "edge", "ran"}

KPI_RULES = [
    {
        "field": "derived_healthScore",
        "op": "lt",
        "threshold": 0.6,
        "label": "health score",
        "unit": "",
    },
    {
        "field": "kpi_packetLossPct",
        "op": "gt",
        "threshold": 1.0,
        "label": "packet loss",
        "unit": "%",
    },
    {
        "field": "kpi_rbUtilizationPct",
        "op": "gt",
        "threshold": 90.0,
        "label": "RB utilization",
        "unit": "%",
    },
    {
        "field": "derived_congestionScore",
        "op": "gt",
        "threshold": 0.8,
        "label": "congestion score",
        "unit": "",
    },
]

CACHE_TTL_SECONDS = 2.0
_cache_lock = threading.Lock()
_cache: Dict[str, Tuple[float, Any]] = {}


class InfluxLogsClient:
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


def normalize_start(start: Optional[str]) -> str:
    return start if start in ALLOWED_STARTS else DEFAULT_START


def parse_categories(categories: Optional[str]) -> List[str]:
    if not categories:
        return []
    parsed: List[str] = []
    for item in categories.split(","):
        value = item.strip().upper()
        if value:
            parsed.append(value)
    return parsed


def validate_categories(categories: Sequence[str]) -> List[str]:
    unknown = sorted({item for item in categories if item not in LOG_CATEGORIES})
    if unknown:
        raise ValueError(f"Unknown categories: {', '.join(unknown)}")
    return list(dict.fromkeys(categories))


def network_logs(
    *,
    scope: str = "national",
    region_id: Optional[str] = None,
    start: str = DEFAULT_START,
    categories: Optional[Sequence[str]] = None,
    min_severity: int = 0,
    entity_id: Optional[str] = None,
    slice_id: Optional[str] = None,
    domain: Optional[str] = None,
    slice_type: Optional[str] = None,
    limit: int = 200,
    cursor: Optional[str] = None,
) -> Dict[str, Any]:
    start = normalize_start(start)
    limit = max(1, min(int(limit), 500))
    min_severity = max(0, min(int(min_severity), 3))
    cat_set = set(validate_categories(categories or []))
    scope = scope if scope in {"national", "regional"} else "national"
    region_key = str(region_id).strip().lower() if region_id is not None else None
    effective_domain = domain.strip().lower() if domain else None
    site_ids: Optional[set[str]] = None

    if scope == "regional":
        if not region_key:
            raise ValueError("region_id is required for regional scope")
        if region_key in DOMAIN_REGION_IDS:
            effective_domain = region_key
        else:
            site_ids = REGION_SITE_IDS.get(region_key, set())
            # TODO: Extend numeric region_id -> site_id/entity mapping when the
            # dashboard-backend taxonomy is backed by real live telemetry tags.

    cache_key = "|".join(
        [
            scope,
            region_key or "",
            start,
            ",".join(sorted(cat_set)),
            str(min_severity),
            entity_id or "",
            slice_id or "",
            effective_domain or "",
            slice_type or "",
            str(limit),
            cursor or "",
        ]
    )

    def build() -> Dict[str, Any]:
        events: List[Dict[str, Any]] = []
        selected = cat_set or LOG_CATEGORIES
        if {"FAULT_OPENED", "FAULT_CLEARED"} & selected:
            events.extend(fetch_fault_events(start=start, cursor=cursor))
        if "KPI_BREACH" in selected:
            events.extend(fetch_kpi_events(start=start, cursor=cursor))
        if {"AIOPS_CONGESTION", "AIOPS_SLA_RISK", "AIOPS_SLICE_MISMATCH"} & selected:
            events.extend(fetch_aiops_events(start=start, cursor=cursor))

        events = _apply_filters(
            events,
            categories=cat_set,
            min_severity=min_severity,
            entity_id=entity_id,
            slice_id=slice_id,
            domain=effective_domain,
            slice_type=slice_type,
            site_ids=site_ids,
        )
        events.sort(key=lambda event: event.get("ts") or "", reverse=True)

        has_more = len(events) > limit
        page = events[:limit]
        return {
            "count": len(page),
            "window": {"start": start, "stop": "now()"},
            "next_cursor": page[-1]["ts"] if has_more and page else None,
            "events": page,
        }

    return _cached(cache_key, build)


def severity_for_event(category: str, raw: Dict[str, Any]) -> int:
    if category.startswith("FAULT_"):
        return _clamp_severity(raw.get("severity"), default=1)

    if category == "KPI_BREACH":
        field = raw.get("field")
        value = _coerce_float(raw.get("value"))
        if value is None:
            return 1
        if field == "derived_healthScore":
            return 3 if value < 0.3 else 2
        if field == "kpi_packetLossPct":
            return 3 if value > 5.0 else 2
        if field == "kpi_rbUtilizationPct":
            return 3 if value > 95.0 else 2
        if field == "derived_congestionScore":
            return 3 if value > 0.9 else 2
        return 1

    if category in {"AIOPS_CONGESTION", "AIOPS_SLA_RISK", "AIOPS_SLICE_MISMATCH"}:
        return _clamp_severity(raw.get("severity"), default=1)

    return 0


def fetch_fault_events(*, start: str, cursor: Optional[str]) -> List[Dict[str, Any]]:
    flux = _faults_flux(InfluxLogsClient().bucket, start, cursor)
    tables = InfluxLogsClient().query(flux)
    rows_by_fault: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for record in _records(tables):
        values = _record_values(record)
        fault_id = _clean(values.get("fault_id")) or "unknown"
        if (_clean(values.get("type")) or "").lower() == "aggregate":
            continue
        ts = _to_iso(_record_time(record))
        if not ts:
            continue
        rows_by_fault[fault_id].append({**values, "ts": ts})

    events: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for fault_id, rows in rows_by_fault.items():
        rows.sort(key=lambda item: item["ts"])
        first = rows[0]
        last = rows[-1]
        events.append(_fault_event("FAULT_OPENED", fault_id, first))

        explicit_clear = next((row for row in rows if _coerce_float(row.get("active")) == 0), None)
        if explicit_clear:
            events.append(_fault_event("FAULT_CLEARED", fault_id, explicit_clear))
            continue

        last_ts = _parse_iso(last.get("ts"))
        if last_ts and now - last_ts > timedelta(seconds=12):
            events.append(_fault_event("FAULT_CLEARED", fault_id, last))

    return events


def fetch_kpi_events(*, start: str, cursor: Optional[str]) -> List[Dict[str, Any]]:
    fields = [rule["field"] for rule in KPI_RULES]
    flux = _measurement_flux(InfluxLogsClient().bucket, "telemetry", start, fields, cursor)
    tables = InfluxLogsClient().query(flux)
    rules = {rule["field"]: rule for rule in KPI_RULES}
    events: List[Dict[str, Any]] = []

    for record in _records(tables):
        values = _record_values(record)
        field = record.get_field()
        rule = rules.get(field)
        value = _coerce_float(record.get_value())
        ts = _to_iso(_record_time(record))
        if not rule or value is None or not ts:
            continue
        if not _threshold_triggered(value, rule):
            continue

        entity_id = _clean(values.get("entity_id"))
        raw = {"field": field, "value": value}
        severity = severity_for_event("KPI_BREACH", raw)
        message = _kpi_message(rule, value, entity_id)
        events.append(
            _event(
                category="KPI_BREACH",
                ts=ts,
                severity=severity,
                domain=_clean(values.get("domain")) or derive_domain(entity_id, _clean(values.get("entity_type"))),
                slice_id=_none_to_null(values.get("slice_id")),
                entity_id=entity_id,
                entity_type=_clean(values.get("entity_type")),
                slice_type=_none_to_null(values.get("slice_type")),
                message=message,
                evidence={
                    "field": field,
                    "value": value,
                    "threshold": rule["threshold"],
                    "operator": rule["op"],
                    "site_id": _clean(values.get("site_id")),
                },
            )
        )

    return events


def fetch_aiops_events(*, start: str, cursor: Optional[str]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    events.extend(
        _fetch_aiops_measurement(
            measurement="aiops_congestion",
            category="AIOPS_CONGESTION",
            alert_prediction="congestion_anomaly",
            score_field="score",
            start=start,
            cursor=cursor,
        )
    )
    events.extend(
        _fetch_aiops_measurement(
            measurement="aiops_sla",
            category="AIOPS_SLA_RISK",
            alert_prediction="sla_at_risk",
            score_field="risk_score",
            start=start,
            cursor=cursor,
        )
    )
    events.extend(
        _fetch_aiops_measurement(
            measurement="aiops_slice_classification",
            category="AIOPS_SLICE_MISMATCH",
            alert_prediction=None,
            score_field="confidence",
            start=start,
            cursor=cursor,
        )
    )
    return events


def _fetch_aiops_measurement(
    *,
    measurement: str,
    category: str,
    alert_prediction: Optional[str],
    score_field: str,
    start: str,
    cursor: Optional[str],
) -> List[Dict[str, Any]]:
    fields = ["prediction", "severity", score_field, "sla_probability"]
    flux = _pivot_flux(InfluxLogsClient().bucket, measurement, start, fields, cursor)
    try:
        tables = InfluxLogsClient().query(flux)
    except Exception as exc:
        logger.warning("AIOps logs query failed for %s: %s", measurement, exc)
        return []

    events: List[Dict[str, Any]] = []
    for record in _records(tables):
        values = _record_values(record)
        prediction = _clean(values.get("prediction"))
        severity = _clamp_severity(values.get("severity"), default=0)
        if category == "AIOPS_SLICE_MISMATCH":
            is_alert = severity > 0 or "mismatch" in (prediction or "").lower()
        else:
            is_alert = prediction == alert_prediction
        ts = _to_iso(_record_time(record))
        if not is_alert or not ts:
            continue

        entity_id = _clean(values.get("entity_id"))
        entity_type = _clean(values.get("entity_type"))
        score = _coerce_float(values.get(score_field))
        message = _aiops_message(category, prediction, entity_id, _none_to_null(values.get("slice_id")), score)
        events.append(
            _event(
                category=category,
                ts=ts,
                severity=severity_for_event(category, {"severity": severity}),
                domain=derive_domain(entity_id, entity_type),
                slice_id=_none_to_null(values.get("slice_id")),
                entity_id=entity_id,
                entity_type=entity_type,
                slice_type=None,
                message=message,
                evidence={
                    "measurement": measurement,
                    "prediction": prediction,
                    "score": score,
                    "sla_probability": _coerce_float(values.get("sla_probability")),
                    "site_id": _clean(values.get("site_id")),
                    "service": _clean(values.get("service")),
                },
            )
        )
    return events


def _fault_event(category: str, fault_id: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    affected = _split_entities(raw.get("affected_entities"))
    entity_id = next((item for item in affected if not item.startswith("slice:")), None)
    slice_id = next((item.split(":", 1)[1] for item in affected if item.startswith("slice:")), None)
    domain = next((derive_domain(item, None) for item in affected if derive_domain(item, None)), None)
    fault_type = _clean(raw.get("fault_type")) or "unknown"
    state = "opened" if category == "FAULT_OPENED" else "cleared"
    target = entity_id or slice_id or "network"
    return _event(
        category=category,
        ts=raw["ts"],
        severity=severity_for_event(category, raw),
        domain=domain,
        slice_id=slice_id,
        entity_id=entity_id,
        entity_type=None,
        slice_type=None,
        message=f"{fault_type} fault {state} on {target}",
        evidence={
            "fault_id": fault_id,
            "fault_type": fault_type,
            "scenario_id": _clean(raw.get("scenario_id")),
            "site_id": _clean(raw.get("site_id")),
            "affected_entities": affected,
            "source": "influx:faults",
        },
    )


def _event(
    *,
    category: str,
    ts: str,
    severity: int,
    domain: Optional[str],
    slice_id: Optional[str],
    entity_id: Optional[str],
    entity_type: Optional[str],
    slice_type: Optional[str],
    message: str,
    evidence: Dict[str, Any],
) -> Dict[str, Any]:
    safe_entity = entity_id or slice_id or "network"
    return {
        "id": f"{category}:{safe_entity}:{ts}",
        "ts": ts,
        "category": category,
        "severity": severity,
        "domain": domain,
        "slice_id": slice_id,
        "entity_id": entity_id,
        "entity_type": entity_type,
        "slice_type": slice_type,
        "message": message,
        "evidence": evidence,
    }


def _apply_filters(
    events: List[Dict[str, Any]],
    *,
    categories: set[str],
    min_severity: int,
    entity_id: Optional[str],
    slice_id: Optional[str],
    domain: Optional[str],
    slice_type: Optional[str],
    site_ids: Optional[set[str]],
) -> List[Dict[str, Any]]:
    filtered = events
    if categories:
        filtered = [event for event in filtered if event["category"] in categories]
    if min_severity > 0:
        filtered = [event for event in filtered if int(event.get("severity") or 0) >= min_severity]
    if entity_id:
        term = entity_id.lower()
        filtered = [event for event in filtered if term in str(event.get("entity_id") or "").lower()]
    if slice_id:
        term = slice_id.lower()
        filtered = [event for event in filtered if term in str(event.get("slice_id") or "").lower()]
    if domain:
        filtered = [event for event in filtered if str(event.get("domain") or "").lower() == domain]
    if slice_type:
        filtered = [event for event in filtered if str(event.get("slice_type") or "").lower() == slice_type.lower()]
    if site_ids is not None:
        filtered = [
            event for event in filtered
            if str((event.get("evidence") or {}).get("site_id") or "") in site_ids
        ]
    return filtered


def derive_domain(entity_id: Optional[str], entity_type: Optional[str]) -> Optional[str]:
    if entity_type:
        mapped = ENTITY_TYPE_TO_DOMAIN.get(entity_type)
        if mapped:
            return mapped
    if entity_id:
        eid = entity_id.lower()
        if eid.startswith("slice-"):
            return "ran"
        if eid.startswith("edge-") or eid.startswith("mec-"):
            return "edge"
        if eid.startswith("gnb-") or eid.startswith("cell-"):
            return "ran"
        if eid.startswith("amf-") or eid.startswith("smf-") or eid.startswith("core-"):
            return "core"
    return None


def _faults_flux(bucket: str, start: str, cursor: Optional[str]) -> str:
    cursor_filter = _cursor_filter(cursor)
    return (
        f'from(bucket: "{_flux_escape(bucket)}")\n'
        f"  |> range(start: {start})\n"
        f'  |> filter(fn: (r) => r._measurement == "faults")\n'
        f'  |> filter(fn: (r) => r._field == "active" or r._field == "severity")\n'
        f"{cursor_filter}"
        f'  |> pivot(rowKey: ["_time", "fault_id"], columnKey: ["_field"], valueColumn: "_value")\n'
    )


def _measurement_flux(bucket: str, measurement: str, start: str, fields: Sequence[str], cursor: Optional[str]) -> str:
    field_filter = " or ".join(f'r._field == "{_flux_escape(field)}"' for field in fields)
    return (
        f'from(bucket: "{_flux_escape(bucket)}")\n'
        f"  |> range(start: {start})\n"
        f'  |> filter(fn: (r) => r._measurement == "{_flux_escape(measurement)}")\n'
        f"  |> filter(fn: (r) => {field_filter})\n"
        f"{_cursor_filter(cursor)}"
    )


def _pivot_flux(bucket: str, measurement: str, start: str, fields: Sequence[str], cursor: Optional[str]) -> str:
    field_filter = " or ".join(f'r._field == "{_flux_escape(field)}"' for field in fields)
    return (
        f'from(bucket: "{_flux_escape(bucket)}")\n'
        f"  |> range(start: {start})\n"
        f'  |> filter(fn: (r) => r._measurement == "{_flux_escape(measurement)}")\n'
        f"  |> filter(fn: (r) => {field_filter})\n"
        f"{_cursor_filter(cursor)}"
        f'  |> pivot(rowKey: ["_time", "entity_id"], columnKey: ["_field"], valueColumn: "_value")\n'
    )


def _cursor_filter(cursor: Optional[str]) -> str:
    if not cursor:
        return ""
    safe_cursor = _flux_escape(cursor)
    return f'  |> filter(fn: (r) => r._time < time(v: "{safe_cursor}"))\n'


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


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _cached(key: str, build: Callable[[], Any]) -> Any:
    now = time.monotonic()
    with _cache_lock:
        entry = _cache.get(key)
        if entry and now - entry[0] < CACHE_TTL_SECONDS:
            return entry[1]
    value = build()
    with _cache_lock:
        _cache[key] = (now, value)
    return value


def _threshold_triggered(value: float, rule: Dict[str, Any]) -> bool:
    if rule["op"] == "lt":
        return value < float(rule["threshold"])
    return value > float(rule["threshold"])


def _kpi_message(rule: Dict[str, Any], value: float, entity_id: Optional[str]) -> str:
    unit = rule.get("unit") or ""
    formatted = f"{value:.2f}{unit}" if abs(value) < 10 else f"{value:.1f}{unit}"
    return f"KPI breach: {rule['label']} {formatted} on {entity_id or 'network'}"


def _aiops_message(
    category: str,
    prediction: Optional[str],
    entity_id: Optional[str],
    slice_id: Optional[str],
    score: Optional[float],
) -> str:
    label = {
        "AIOPS_CONGESTION": "Congestion anomaly",
        "AIOPS_SLA_RISK": "SLA risk",
        "AIOPS_SLICE_MISMATCH": "Slice classification mismatch",
    }.get(category, category)
    score_text = f" score={score:.2f}" if score is not None else ""
    return f"{label} on {entity_id or slice_id or 'network'} ({prediction or 'unknown'}{score_text})"


def _split_entities(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).replace(";", ",").split(",") if item.strip()]


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


def _clamp_severity(value: Any, default: int = 0) -> int:
    coerced = _coerce_float(value)
    if coerced is None:
        return default
    return max(0, min(int(coerced), 3))


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _none_to_null(value: Any) -> Optional[str]:
    text = _clean(value)
    if not text or text.lower() == "none":
        return None
    return text


def _flux_escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')
