"""Configuration for the sla-assurance runtime service."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _as_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class SlaAssuranceConfig:
    service_name: str = field(default_factory=lambda: os.getenv("SERVICE_NAME", "sla-assurance"))

    redis_host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "redis"))
    redis_port: int = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    redis_db: int = field(default_factory=lambda: int(os.getenv("REDIS_DB", "0")))
    stream_maxlen: int = field(default_factory=lambda: int(os.getenv("STREAM_MAXLEN", "10000")))

    input_stream: str = field(default_factory=lambda: os.getenv("INPUT_STREAM", "stream:norm.telemetry"))
    consumer_group: str = field(default_factory=lambda: os.getenv("CONSUMER_GROUP", "aiops-sla-group"))
    consumer_name: str = field(default_factory=lambda: os.getenv("CONSUMER_NAME", "sla-assurance-01"))
    read_count: int = field(default_factory=lambda: int(os.getenv("READ_COUNT", "32")))
    block_ms: int = field(default_factory=lambda: int(os.getenv("BLOCK_MS", "1000")))

    output_stream: str = field(default_factory=lambda: os.getenv("OUTPUT_STREAM", "events.sla"))
    kafka_enabled: bool = field(default_factory=lambda: _as_bool("KAFKA_ENABLED", True))
    kafka_broker: str = field(default_factory=lambda: os.getenv("KAFKA_BROKER", "kafka:9092"))
    kafka_topic: str = field(default_factory=lambda: os.getenv("KAFKA_TOPIC", "events.sla"))

    state_prefix: str = field(default_factory=lambda: os.getenv("STATE_PREFIX", "aiops:sla"))
    state_ttl_sec: int = field(default_factory=lambda: int(os.getenv("STATE_TTL_SEC", "7200")))

    influx_enabled: bool = field(default_factory=lambda: _as_bool("INFLUXDB_ENABLED", True))
    influx_url: str = field(default_factory=lambda: os.getenv("INFLUXDB_URL", "http://influxdb:8086"))
    influx_token: str = field(default_factory=lambda: os.getenv("INFLUXDB_TOKEN", "neuroslice_token_12345"))
    influx_org: str = field(default_factory=lambda: os.getenv("INFLUXDB_ORG", "neuroslice"))
    influx_bucket: str = field(default_factory=lambda: os.getenv("INFLUXDB_BUCKET", "telemetry"))
    influx_measurement: str = field(default_factory=lambda: os.getenv("INFLUX_MEASUREMENT", "aiops_sla"))

    model_name: str = field(default_factory=lambda: os.getenv("SLA_MODEL_NAME", "sla-xgboost-5g"))
    model_path: str = field(default_factory=lambda: os.getenv("SLA_MODEL_PATH", ""))
    model_version: str = field(default_factory=lambda: os.getenv("SLA_MODEL_VERSION", ""))
    mlflow_db_path: str = field(default_factory=lambda: os.getenv("MLFLOW_DB_PATH", "/mlops/mlflow.db"))
    mlruns_dir: str = field(default_factory=lambda: os.getenv("MLRUNS_DIR", "/mlops/mlruns"))
    model_registry_path: str = field(
        default_factory=lambda: os.getenv("MODEL_REGISTRY_PATH", "/mlops/models/registry.json")
    )
    model_poll_interval_sec: int = field(
        default_factory=lambda: int(os.getenv("MODEL_POLL_INTERVAL_SEC", "60"))
    )
    registry_model_name: str = field(default_factory=lambda: os.getenv("MODEL_NAME", "sla_5g"))
    model_format: str = field(default_factory=lambda: os.getenv("MODEL_FORMAT", "onnx_fp16"))
    mlflow_tracking_uri: str = field(default_factory=lambda: os.getenv("MLFLOW_TRACKING_URI", ""))
    scaler_path: str = field(
        default_factory=lambda: os.getenv("SLA_SCALER_PATH", "/mlops/data/processed/scaler_sla_5g.pkl")
    )
    metrics_port: int = field(default_factory=lambda: int(os.getenv("METRICS_PORT", "9102")))

    sla_risk_threshold: float = field(default_factory=lambda: float(os.getenv("SLA_RISK_THRESHOLD", "0.5")))
    default_site_id: str = field(default_factory=lambda: os.getenv("SITE_ID", "TT-SFAX-02"))


_CONFIG: SlaAssuranceConfig | None = None


def get_config() -> SlaAssuranceConfig:
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = SlaAssuranceConfig()
    return _CONFIG
