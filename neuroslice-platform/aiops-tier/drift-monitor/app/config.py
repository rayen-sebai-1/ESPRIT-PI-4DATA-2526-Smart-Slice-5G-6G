"""Configuration for drift-monitor service."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class DriftConfig:
    service_name: str = ""
    runtime_service_name: str = ""
    service_port: int = 0

    redis_host: str = ""
    redis_port: int = 0

    input_stream: str = ""
    output_stream: str = ""
    consumer_group: str = ""
    consumer_name: str = ""
    read_count: int = 0
    block_ms: int = 0

    kafka_broker: str = ""
    kafka_drift_topic: str = ""

    influxdb_url: str = ""
    influxdb_token: str = ""
    influxdb_org: str = ""
    influxdb_bucket: str = ""

    drift_method: str = ""
    drift_window_size: int = 0
    drift_p_value_threshold: float = 0.0
    drift_min_reference_samples: int = 0
    drift_test_interval_sec: float = 0.0
    drift_emit_cooldown_sec: float = 0.0
    drift_require_references: bool = False
    drift_auto_trigger_mlops: bool = False

    models_base_path: str = ""

    def __post_init__(self) -> None:
        self.service_name = os.environ.get("SERVICE_NAME", "drift-monitor")
        self.runtime_service_name = os.environ.get(
            "RUNTIME_SERVICE_NAME",
            "aiops-drift-monitor",
        )
        self.service_port = int(os.environ.get("SERVICE_PORT", "7012"))

        self.redis_host = os.environ.get("REDIS_HOST", "redis")
        self.redis_port = int(os.environ.get("REDIS_PORT", "6379"))

        self.input_stream = os.environ.get("INPUT_STREAM", "stream:norm.telemetry")
        self.output_stream = os.environ.get("OUTPUT_STREAM", "events.drift")
        self.consumer_group = os.environ.get("CONSUMER_GROUP", "aiops-drift-group")
        self.consumer_name = os.environ.get("CONSUMER_NAME", "drift-monitor-01")
        self.read_count = int(os.environ.get("READ_COUNT", "50"))
        self.block_ms = int(os.environ.get("BLOCK_MS", "1000"))

        self.kafka_broker = os.environ.get("KAFKA_BROKER", "kafka:9092")
        self.kafka_drift_topic = os.environ.get("KAFKA_DRIFT_TOPIC", "drift.alert")

        self.influxdb_url = os.environ.get("INFLUXDB_URL", "http://influxdb:8086")
        self.influxdb_token = os.environ.get("INFLUXDB_TOKEN", "neuroslice_token_12345")
        self.influxdb_org = os.environ.get("INFLUXDB_ORG", "neuroslice")
        self.influxdb_bucket = os.environ.get("INFLUXDB_BUCKET", "telemetry")

        self.drift_method = os.environ.get("DRIFT_METHOD", "mmd")
        self.drift_window_size = int(os.environ.get("DRIFT_WINDOW_SIZE", "500"))
        self.drift_p_value_threshold = float(os.environ.get("DRIFT_P_VALUE_THRESHOLD", "0.01"))
        self.drift_min_reference_samples = int(os.environ.get("DRIFT_MIN_REFERENCE_SAMPLES", "500"))
        self.drift_test_interval_sec = float(os.environ.get("DRIFT_TEST_INTERVAL_SEC", "60"))
        self.drift_emit_cooldown_sec = float(os.environ.get("DRIFT_EMIT_COOLDOWN_SEC", "300"))
        self.drift_require_references = (
            os.environ.get("DRIFT_REQUIRE_REFERENCES", "false").lower() == "true"
        )
        self.drift_auto_trigger_mlops = (
            os.environ.get("DRIFT_AUTO_TRIGGER_MLOPS", "false").lower() == "true"
        )
        self.models_base_path = os.environ.get("MODELS_BASE_PATH", "/mlops/models/promoted")

    @property
    def drift_model_names(self) -> list[str]:
        raw = os.environ.get("DRIFT_MODEL_NAMES", "congestion_5g,sla_5g,slice_type_5g")
        return [m.strip() for m in raw.split(",") if m.strip()]


_cfg: DriftConfig | None = None


def get_config() -> DriftConfig:
    global _cfg
    if _cfg is None:
        _cfg = DriftConfig()
    return _cfg
