"""Configuration for the deterministic Alert Management service."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _csv(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass
class AlertManagementConfig:
    service_name: str = field(default_factory=lambda: os.getenv("SERVICE_NAME", "alert-management"))
    service_port: int = field(default_factory=lambda: int(os.getenv("SERVICE_PORT", "7010")))

    redis_host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "redis"))
    redis_port: int = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    redis_db: int = field(default_factory=lambda: int(os.getenv("REDIS_DB", "0")))

    input_streams: list[str] = field(
        default_factory=lambda: _csv(
            "INPUT_STREAMS",
            "events.anomaly,events.sla,events.slice.classification",
        )
    )
    output_stream: str = field(default_factory=lambda: os.getenv("OUTPUT_STREAM", "stream:control.alerts"))
    consumer_group: str = field(
        default_factory=lambda: os.getenv("CONSUMER_GROUP", "control-alert-management-group")
    )
    consumer_name: str = field(default_factory=lambda: os.getenv("CONSUMER_NAME", "alert-management-01"))
    read_count: int = field(default_factory=lambda: int(os.getenv("READ_COUNT", "32")))
    block_ms: int = field(default_factory=lambda: int(os.getenv("BLOCK_MS", "1000")))
    stream_maxlen: int = field(default_factory=lambda: int(os.getenv("STREAM_MAXLEN", "10000")))


_CONFIG: AlertManagementConfig | None = None


def get_config() -> AlertManagementConfig:
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = AlertManagementConfig()
    return _CONFIG
