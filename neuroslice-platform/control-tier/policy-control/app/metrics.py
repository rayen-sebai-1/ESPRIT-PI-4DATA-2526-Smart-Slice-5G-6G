"""Prometheus metrics for policy-control service."""
from __future__ import annotations

import time
from typing import Any

from prometheus_client import Counter, Gauge

control_actions_total = Counter(
    "neuroslice_control_actions_total",
    "Total control actions by action type and status",
    ["action_type", "status"],
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


def record_action_state(action: dict[str, Any]) -> None:
    action_type = str(action.get("action_type") or "UNKNOWN")
    status = str(action.get("status") or "UNKNOWN")
    control_actions_total.labels(action_type=action_type, status=status).inc()


def mark_event_processed(service_name: str) -> None:
    control_events_processed_total.labels(service=service_name).inc()
    control_last_event_timestamp.labels(service=service_name).set(time.time())
