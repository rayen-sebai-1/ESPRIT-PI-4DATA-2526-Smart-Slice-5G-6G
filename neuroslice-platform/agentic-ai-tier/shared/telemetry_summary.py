from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import math
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Tuple


GREATER_THAN_THRESHOLDS = {
    "kpi_packetLossPct": 2.0,
    "kpi_forwardingLatencyMs": 20.0,
    "kpi_rbUtilizationPct": 85.0,
    "kpi_cpuUtilPct": 85.0,
    "derived_congestionScore": 0.75,
    "derived_misroutingScore": 0.5,
    "severity": 3.0,
}

LESS_THAN_THRESHOLDS = {
    "derived_healthScore": 0.7,
}

GROUP_KEYS = ("slice_id", "domain", "entity_id", "entity_type", "slice_type", "field")
POINT_KEYS = ("timestamp", "slice_id", "domain", "entity_id", "entity_type", "slice_type")


def summarize_telemetry_records(
    records: Iterable[Dict[str, Any]],
    time_range: Optional[Dict[str, str]] = None,
    filters: Optional[Dict[str, Any]] = None,
    max_groups: int = 35,
) -> Dict[str, Any]:
    rows = list(records)
    normalized_time_range = time_range or {"start": "-30m", "stop": "now()"}
    normalized_filters = {key: value for key, value in (filters or {}).items() if value not in (None, "")}

    if not rows:
        return empty_telemetry_summary(
            time_range=normalized_time_range,
            filters=normalized_filters,
        )

    grouped: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)
    unique_points = set()
    timestamps: List[str] = []

    for index, row in enumerate(rows):
        field = str(row.get("field") or "").strip()
        if not field:
            continue

        timestamp = _timestamp_to_string(row.get("timestamp"))
        if timestamp:
            timestamps.append(timestamp)

        group_key = tuple(_clean_dimension(row.get(key)) for key in GROUP_KEYS)
        point_key = tuple(_clean_dimension(row.get(key)) for key in POINT_KEYS)
        unique_points.add(point_key or index)

        grouped[group_key].append(
            {
                "timestamp": timestamp,
                "field": field,
                "value": row.get("value"),
                "index": index,
            }
        )

    group_summaries: List[Dict[str, Any]] = []
    entity_scores: Dict[Tuple[Any, ...], Dict[str, Any]] = {}

    for group_key, samples in grouped.items():
        summary = _summarize_group(group_key, samples)
        if summary is None:
            continue

        group_summaries.append(summary)
        _update_entity_score(entity_scores, summary)

    group_summaries.sort(key=_group_sort_key, reverse=True)
    top_groups = group_summaries[: max(1, max_groups)]

    top_breached_kpis = [
        _strip_samples(group)
        for group in group_summaries
        if int(group.get("breach_count") or 0) > 0
    ][:15]

    top_anomalous_entities = sorted(
        (_finalize_entity_score(value) for value in entity_scores.values()),
        key=lambda item: (
            item.get("breach_count", 0),
            item.get("max_severity", 0),
            item.get("anomaly_score", 0),
        ),
        reverse=True,
    )[:10]

    return {
        "status": "ok" if group_summaries else "no_data",
        "measurement": "telemetry",
        "time_range": normalized_time_range,
        "filters": normalized_filters,
        "summary": {
            "total_points_seen": len(unique_points),
            "total_field_values_seen": len(rows),
            "groups_returned": len(top_groups),
            "top_anomalous_entities": top_anomalous_entities,
            "top_breached_kpis": top_breached_kpis,
            "window_start": min(timestamps) if timestamps else normalized_time_range.get("start"),
            "window_stop": max(timestamps) if timestamps else normalized_time_range.get("stop"),
        },
        "groups": top_groups,
    }


def empty_telemetry_summary(
    time_range: Optional[Dict[str, str]] = None,
    filters: Optional[Dict[str, Any]] = None,
    note: str = "No telemetry points matched the requested filters.",
) -> Dict[str, Any]:
    normalized_time_range = time_range or {"start": "-30m", "stop": "now()"}
    return {
        "status": "no_data",
        "measurement": "telemetry",
        "time_range": normalized_time_range,
        "filters": filters or {},
        "summary": {
            "total_points_seen": 0,
            "total_field_values_seen": 0,
            "groups_returned": 0,
            "top_anomalous_entities": [],
            "top_breached_kpis": [],
            "window_start": normalized_time_range.get("start"),
            "window_stop": normalized_time_range.get("stop"),
            "note": note,
        },
        "groups": [],
    }


def _summarize_group(group_key: Tuple[Any, ...], samples: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    slice_id, domain, entity_id, entity_type, slice_type, field = group_key
    ordered = sorted(samples, key=lambda item: (item.get("timestamp") or "", item.get("index", 0)))

    numeric_samples = []
    for sample in ordered:
        value = _safe_float(sample.get("value"))
        if value is None:
            continue
        numeric_samples.append(
            {
                "timestamp": sample.get("timestamp"),
                "value": value,
            }
        )

    if not numeric_samples:
        return None

    values = [sample["value"] for sample in numeric_samples]
    breach_samples = [sample for sample in numeric_samples if _is_breach(str(field), sample["value"])]
    first_value = values[0]
    last_value = values[-1]
    slope_simple = (last_value - first_value) / max(1, len(values) - 1)
    group = {
        "slice_id": slice_id,
        "domain": domain,
        "entity_id": entity_id,
        "entity_type": entity_type,
        "slice_type": slice_type,
        "field": field,
        "count": len(values),
        "min": _round_number(min(values)),
        "max": _round_number(max(values)),
        "mean": _round_number(mean(values)),
        "last": _round_number(last_value),
        "p95": _round_number(_percentile(values, 95)),
        "first_timestamp": numeric_samples[0].get("timestamp"),
        "last_timestamp": numeric_samples[-1].get("timestamp"),
        "trend": _classify_trend(values),
        "slope_simple": _round_number(slope_simple),
        "breach_count": len(breach_samples),
        "first_breach_timestamp": breach_samples[0].get("timestamp") if breach_samples else None,
        "last_breach_timestamp": breach_samples[-1].get("timestamp") if breach_samples else None,
        "priority_score": _round_number(_priority_score(str(field), values, len(breach_samples))),
    }

    if len(breach_samples) > 0 or str(field).startswith("derived_") or str(field) == "severity":
        group["samples"] = _representative_samples(numeric_samples)

    return group


def _classify_trend(values: List[float]) -> str:
    if len(values) < 2:
        return "stable"

    deltas = [values[index] - values[index - 1] for index in range(1, len(values))]
    meaningful = [delta for delta in deltas if abs(delta) > max(abs(mean(values)) * 0.01, 0.005)]
    sign_changes = 0
    previous_sign = 0
    for delta in meaningful:
        sign = 1 if delta > 0 else -1
        if previous_sign and sign != previous_sign:
            sign_changes += 1
        previous_sign = sign

    amplitude = max(values) - min(values)
    if len(values) >= 4 and sign_changes >= 2 and amplitude > max(abs(mean(values)) * 0.1, 0.05):
        return "volatile"

    slope_simple = (values[-1] - values[0]) / max(1, len(values) - 1)
    stable_threshold = max(abs(mean(values)) * 0.03, 0.01)
    if abs(slope_simple) <= stable_threshold:
        return "stable"
    return "increasing" if slope_simple > 0 else "decreasing"


def _is_breach(field: str, value: float) -> bool:
    if field in GREATER_THAN_THRESHOLDS:
        return value >= GREATER_THAN_THRESHOLDS[field]
    if field in LESS_THAN_THRESHOLDS:
        return value <= LESS_THAN_THRESHOLDS[field]
    return False


def _priority_score(field: str, values: List[float], breach_count: int) -> float:
    peak = max(values)
    latest = values[-1]
    if field == "derived_healthScore":
        metric_score = max(0.0, 1.0 - min(values))
    elif field == "severity":
        metric_score = peak / 4.0
    elif field.startswith("derived_"):
        metric_score = peak
    else:
        metric_score = peak / 100.0 if peak > 1 else peak
    return float(breach_count) + max(metric_score, latest if latest <= 1 else latest / 100.0)


def _update_entity_score(entity_scores: Dict[Tuple[Any, ...], Dict[str, Any]], group: Dict[str, Any]) -> None:
    key = (
        group.get("slice_id"),
        group.get("domain"),
        group.get("entity_id"),
        group.get("entity_type"),
        group.get("slice_type"),
    )
    current = entity_scores.setdefault(
        key,
        {
            "slice_id": group.get("slice_id"),
            "domain": group.get("domain"),
            "entity_id": group.get("entity_id"),
            "entity_type": group.get("entity_type"),
            "slice_type": group.get("slice_type"),
            "breach_count": 0,
            "max_severity": 0.0,
            "max_congestion_score": 0.0,
            "max_misrouting_score": 0.0,
            "min_health_score": None,
            "fields": set(),
        },
    )

    breach_count = int(group.get("breach_count") or 0)
    current["breach_count"] += breach_count
    if breach_count > 0:
        current["fields"].add(group.get("field"))

    field = group.get("field")
    if field == "severity":
        current["max_severity"] = max(float(current["max_severity"]), float(group.get("max") or 0))
    elif field == "derived_congestionScore":
        current["max_congestion_score"] = max(float(current["max_congestion_score"]), float(group.get("max") or 0))
    elif field == "derived_misroutingScore":
        current["max_misrouting_score"] = max(float(current["max_misrouting_score"]), float(group.get("max") or 0))
    elif field == "derived_healthScore":
        min_health = float(group.get("min") or 0)
        current["min_health_score"] = min_health if current["min_health_score"] is None else min(
            float(current["min_health_score"]),
            min_health,
        )


def _finalize_entity_score(value: Dict[str, Any]) -> Dict[str, Any]:
    min_health = value.get("min_health_score")
    health_risk = 0.0 if min_health is None else max(0.0, 1.0 - float(min_health))
    anomaly_score = max(
        float(value.get("max_severity") or 0) / 4.0,
        float(value.get("max_congestion_score") or 0),
        float(value.get("max_misrouting_score") or 0),
        health_risk,
    )

    return {
        "slice_id": value.get("slice_id"),
        "domain": value.get("domain"),
        "entity_id": value.get("entity_id"),
        "entity_type": value.get("entity_type"),
        "slice_type": value.get("slice_type"),
        "breach_count": int(value.get("breach_count") or 0),
        "max_severity": _round_number(float(value.get("max_severity") or 0)),
        "anomaly_score": _round_number(anomaly_score),
        "breached_fields": sorted(str(item) for item in value.get("fields", set()) if item),
    }


def _representative_samples(samples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not samples:
        return []
    candidates = [samples[0], max(samples, key=lambda item: item.get("value") or 0), samples[-1]]
    seen = set()
    result = []
    for sample in candidates:
        key = (sample.get("timestamp"), sample.get("value"))
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "timestamp": sample.get("timestamp"),
                "value": _round_number(float(sample.get("value") or 0)),
            }
        )
    return result[:3]


def _percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]

    rank = (percentile / 100.0) * (len(ordered) - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[int(rank)]
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _group_sort_key(group: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        int(group.get("breach_count") or 0),
        float(group.get("priority_score") or 0),
        float(group.get("max") or 0),
        str(group.get("last_timestamp") or ""),
    )


def _strip_samples(group: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in group.items()
        if key not in {"samples"}
    }


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(converted) or math.isinf(converted):
        return None
    return converted


def _round_number(value: float) -> float:
    return round(float(value), 4)


def _timestamp_to_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    return str(value)


def _clean_dimension(value: Any) -> Any:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nil"}:
        return None
    return text
