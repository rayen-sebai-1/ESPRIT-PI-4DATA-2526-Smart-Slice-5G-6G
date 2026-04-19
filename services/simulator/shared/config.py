"""
shared/config.py
Central configuration loader for all neuroslice-sim services.
Values are read from environment variables with sensible defaults.
"""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SimulatorConfig:
    # Redis
    redis_host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "redis"))
    redis_port: int = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    redis_db: int = field(default_factory=lambda: int(os.getenv("REDIS_DB", "0")))
    stream_maxlen: int = field(default_factory=lambda: int(os.getenv("STREAM_MAXLEN", "10000")))

    # Simulation timing
    tick_interval_sec: float = field(default_factory=lambda: float(os.getenv("TICK_INTERVAL_SEC", "2.0")))
    sim_speed: float = field(default_factory=lambda: float(os.getenv("SIM_SPEED", "60.0")))  # sim-sec per real-sec

    # Service identity
    service_name: str = field(default_factory=lambda: os.getenv("SERVICE_NAME", "unknown"))
    site_id: str = field(default_factory=lambda: os.getenv("SITE_ID", "TT-SFAX-02"))

    # Adapter endpoints
    ves_adapter_url: str = field(default_factory=lambda: os.getenv("VES_ADAPTER_URL", "http://adapter-ves:7001"))
    netconf_adapter_url: str = field(default_factory=lambda: os.getenv("NETCONF_ADAPTER_URL", "http://adapter-netconf:7002"))
    normalizer_url: str = field(default_factory=lambda: os.getenv("NORMALIZER_URL", "http://normalizer:7003"))
    fault_engine_url: str = field(default_factory=lambda: os.getenv("FAULT_ENGINE_URL", "http://fault-engine:7004"))

    # Stream names
    stream_norm_telemetry: str = "stream:norm.telemetry"
    stream_fault_events: str = "stream:fault.events"
    stream_alerts: str = "stream:alerts"
    stream_entity_state: str = "stream:entity.state"
    stream_raw_ves: str = "stream:raw.ves"
    stream_raw_netconf: str = "stream:raw.netconf"

    # Prometheus
    metrics_port: int = field(default_factory=lambda: int(os.getenv("METRICS_PORT", "9090")))


# Singleton config instance
_config: Optional[SimulatorConfig] = None


def get_config() -> SimulatorConfig:
    global _config
    if _config is None:
        _config = SimulatorConfig()
    return _config
