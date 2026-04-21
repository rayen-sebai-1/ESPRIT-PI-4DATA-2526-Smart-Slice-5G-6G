"""Configuration for the slice-classifier runtime service."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _as_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class SliceClassifierConfig:
    service_name: str = field(default_factory=lambda: os.getenv("SERVICE_NAME", "slice-classifier"))

    redis_host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "redis"))
    redis_port: int = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    redis_db: int = field(default_factory=lambda: int(os.getenv("REDIS_DB", "0")))
    stream_maxlen: int = field(default_factory=lambda: int(os.getenv("STREAM_MAXLEN", "10000")))

    input_stream: str = field(default_factory=lambda: os.getenv("INPUT_STREAM", "stream:norm.telemetry"))
    consumer_group: str = field(default_factory=lambda: os.getenv("CONSUMER_GROUP", "aiops-slice-group"))
    consumer_name: str = field(default_factory=lambda: os.getenv("CONSUMER_NAME", "slice-classifier-01"))
    read_count: int = field(default_factory=lambda: int(os.getenv("READ_COUNT", "32")))
    block_ms: int = field(default_factory=lambda: int(os.getenv("BLOCK_MS", "1000")))

    output_stream: str = field(default_factory=lambda: os.getenv("OUTPUT_STREAM", "events.slice.classification"))
    kafka_enabled: bool = field(default_factory=lambda: _as_bool("KAFKA_ENABLED", True))
    kafka_broker: str = field(default_factory=lambda: os.getenv("KAFKA_BROKER", "kafka:9092"))
    kafka_topic: str = field(default_factory=lambda: os.getenv("KAFKA_TOPIC", "events.slice.classification"))

    state_prefix: str = field(default_factory=lambda: os.getenv("STATE_PREFIX", "aiops:slice_classification"))
    state_ttl_sec: int = field(default_factory=lambda: int(os.getenv("STATE_TTL_SEC", "7200")))

    influx_enabled: bool = field(default_factory=lambda: _as_bool("INFLUXDB_ENABLED", True))
    influx_url: str = field(default_factory=lambda: os.getenv("INFLUXDB_URL", "http://influxdb:8086"))
    influx_token: str = field(default_factory=lambda: os.getenv("INFLUXDB_TOKEN", "neuroslice_token_12345"))
    influx_org: str = field(default_factory=lambda: os.getenv("INFLUXDB_ORG", "neuroslice"))
    influx_bucket: str = field(default_factory=lambda: os.getenv("INFLUXDB_BUCKET", "telemetry"))
    influx_measurement: str = field(default_factory=lambda: os.getenv("INFLUX_MEASUREMENT", "aiops_slice_classification"))

    model_name: str = field(default_factory=lambda: os.getenv("SLICE_MODEL_NAME", "slice-type-lgbm-5g"))
    model_path: str = field(default_factory=lambda: os.getenv("SLICE_MODEL_PATH", ""))
    model_version: str = field(default_factory=lambda: os.getenv("SLICE_MODEL_VERSION", ""))
    mlflow_db_path: str = field(default_factory=lambda: os.getenv("MLFLOW_DB_PATH", "/mlops/mlflow.db"))
    mlruns_dir: str = field(default_factory=lambda: os.getenv("MLRUNS_DIR", "/mlops/mlruns"))
    label_encoder_path: str = field(
        default_factory=lambda: os.getenv(
            "SLICE_LABEL_ENCODER_PATH", "/mlops/data/processed/label_encoder_slice_type_5g.pkl"
        )
    )

    mismatch_confidence_threshold: float = field(
        default_factory=lambda: float(os.getenv("SLICE_MISMATCH_CONFIDENCE_THRESHOLD", "0.8"))
    )
    default_site_id: str = field(default_factory=lambda: os.getenv("SITE_ID", "TT-SFAX-02"))


_CONFIG: SliceClassifierConfig | None = None


def get_config() -> SliceClassifierConfig:
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = SliceClassifierConfig()
    return _CONFIG
