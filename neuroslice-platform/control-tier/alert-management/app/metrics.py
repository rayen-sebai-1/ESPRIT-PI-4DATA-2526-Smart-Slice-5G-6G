"""Prometheus metrics for alert-management service."""
from __future__ import annotations

import time
from typing import Any

from prometheus_client import Counter, Gauge

control_alerts_total = Counter(
    "neuroslice_control_alerts_total",
    "Total control alerts by severity/type/status",
    ["severity", "type", "status"],
)

control_events_processed_total = Counter(
    "neuroslice_control_events_processed_total",
    "Total events processed by control-tier service",
    ["service"],
)

control_last_event_timestamp = Gauge(
    "neuroslice_control_last_event_timestamp",
    "Unix timestamp of the last processed control-tier event",
    ["service"],
)


def record_alert_state(alert: dict[str, Any]) -> None:
    severity = str(alert.get("severity") or "UNKNOWN")
    alert_type = str(alert.get("alert_type") or "UNKNOWN")
    status = str(alert.get("status") or "UNKNOWN")
    control_alerts_total.labels(severity=severity, type=alert_type, status=status).inc()


def mark_event_processed(service_name: str) -> None:
    control_events_processed_total.labels(service=service_name).inc()
    control_last_event_timestamp.labels(service=service_name).set(time.time())
