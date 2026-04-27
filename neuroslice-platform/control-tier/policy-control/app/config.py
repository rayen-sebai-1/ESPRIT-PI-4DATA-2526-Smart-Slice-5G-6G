"""Configuration for the deterministic Policy Control service."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class PolicyControlConfig:
    service_name: str = field(default_factory=lambda: os.getenv("SERVICE_NAME", "policy-control"))
    service_port: int = field(default_factory=lambda: int(os.getenv("SERVICE_PORT", "7011")))

    redis_host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "redis"))
    redis_port: int = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    redis_db: int = field(default_factory=lambda: int(os.getenv("REDIS_DB", "0")))

    input_stream: str = field(default_factory=lambda: os.getenv("INPUT_STREAM", "stream:control.alerts"))
    output_stream: str = field(default_factory=lambda: os.getenv("OUTPUT_STREAM", "stream:control.actions"))
    consumer_group: str = field(default_factory=lambda: os.getenv("CONSUMER_GROUP", "control-policy-group"))
    consumer_name: str = field(default_factory=lambda: os.getenv("CONSUMER_NAME", "policy-control-01"))
    read_count: int = field(default_factory=lambda: int(os.getenv("READ_COUNT", "32")))
    block_ms: int = field(default_factory=lambda: int(os.getenv("BLOCK_MS", "1000")))
    stream_maxlen: int = field(default_factory=lambda: int(os.getenv("STREAM_MAXLEN", "10000")))


_CONFIG: PolicyControlConfig | None = None


def get_config() -> PolicyControlConfig:
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = PolicyControlConfig()
    return _CONFIG
