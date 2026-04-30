"""Configuration for the congestion-detector runtime service."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _as_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class CongestionConfig:
    service_name: str = field(default_factory=lambda: os.getenv("SERVICE_NAME", "congestion-detector"))

    redis_host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "redis"))
    redis_port: int = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    redis_db: int = field(default_factory=lambda: int(os.getenv("REDIS_DB", "0")))
    stream_maxlen: int = field(default_factory=lambda: int(os.getenv("STREAM_MAXLEN", "10000")))

    input_stream: str = field(default_factory=lambda: os.getenv("INPUT_STREAM", "stream:norm.telemetry"))
    consumer_group: str = field(default_factory=lambda: os.getenv("CONSUMER_GROUP", "aiops-congestion-group"))
    consumer_name: str = field(default_factory=lambda: os.getenv("CONSUMER_NAME", "congestion-detector-01"))
    read_count: int = field(default_factory=lambda: int(os.getenv("READ_COUNT", "32")))
    block_ms: int = field(default_factory=lambda: int(os.getenv("BLOCK_MS", "1000")))

    output_stream: str = field(default_factory=lambda: os.getenv("OUTPUT_STREAM", "events.anomaly"))
    kafka_enabled: bool = field(default_factory=lambda: _as_bool("KAFKA_ENABLED", True))
    kafka_broker: str = field(default_factory=lambda: os.getenv("KAFKA_BROKER", "kafka:9092"))
    kafka_topic: str = field(default_factory=lambda: os.getenv("KAFKA_TOPIC", "events.anomaly"))

    state_prefix: str = field(default_factory=lambda: os.getenv("STATE_PREFIX", "aiops:congestion"))
    state_ttl_sec: int = field(default_factory=lambda: int(os.getenv("STATE_TTL_SEC", "7200")))

    influx_enabled: bool = field(default_factory=lambda: _as_bool("INFLUXDB_ENABLED", True))
    influx_url: str = field(default_factory=lambda: os.getenv("INFLUXDB_URL", "http://influxdb:8086"))
    influx_token: str = field(default_factory=lambda: os.getenv("INFLUXDB_TOKEN", "neuroslice_token_12345"))
    influx_org: str = field(default_factory=lambda: os.getenv("INFLUXDB_ORG", "neuroslice"))
    influx_bucket: str = field(default_factory=lambda: os.getenv("INFLUXDB_BUCKET", "telemetry"))
    influx_measurement: str = field(default_factory=lambda: os.getenv("INFLUX_MEASUREMENT", "aiops_congestion"))

    model_path: str = field(
        default_factory=lambda: os.getenv(
            "CONGESTION_MODEL_PATH", "/mlops/models/congestion_5g_lstm_traced.pt"
        )
    )
    preprocessor_path: str = field(
        default_factory=lambda: os.getenv(
            "CONGESTION_PREPROCESSOR_PATH", "/mlops/data/processed/preprocessor_congestion_5g.pkl"
        )
    )
    model_version: str = field(default_factory=lambda: os.getenv("CONGESTION_MODEL_VERSION", ""))
    model_registry_path: str = field(
        default_factory=lambda: os.getenv("MODEL_REGISTRY_PATH", "/mlops/models/registry.json")
    )
    model_poll_interval_sec: int = field(
        default_factory=lambda: int(os.getenv("MODEL_POLL_INTERVAL_SEC", "60"))
    )
    registry_model_name: str = field(default_factory=lambda: os.getenv("MODEL_NAME", "congestion_5g"))
    model_format: str = field(default_factory=lambda: os.getenv("MODEL_FORMAT", "onnx_fp16"))
    mlflow_tracking_uri: str = field(default_factory=lambda: os.getenv("MLFLOW_TRACKING_URI", ""))
    default_site_id: str = field(default_factory=lambda: os.getenv("SITE_ID", "TT-SFAX-02"))
    metrics_port: int = field(default_factory=lambda: int(os.getenv("METRICS_PORT", "9101")))

    sequence_length: int = field(default_factory=lambda: int(os.getenv("CONGESTION_SEQUENCE_LENGTH", "30")))
    congestion_threshold: float = field(default_factory=lambda: float(os.getenv("CONGESTION_THRESHOLD", "0.5")))


_CONFIG: CongestionConfig | None = None


def get_config() -> CongestionConfig:
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = CongestionConfig()
    return _CONFIG
