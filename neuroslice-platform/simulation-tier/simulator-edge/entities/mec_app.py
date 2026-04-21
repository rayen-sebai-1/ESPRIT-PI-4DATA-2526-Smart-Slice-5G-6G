"""
simulator-edge/entities/mec_app.py
MEC Application stateful entity.

App latency and error rate depend on compute node saturation
and incoming request rate (driven by UE count).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict


@dataclass
class MECAppState:
    app_id: str = "mec-app-01"

    # Latent state
    request_rate: float = 200.0          # req/s
    active_connections: float = 150.0
    response_time_ms: float = 5.0
    error_rate: float = 0.002
    cpu_util: float = 0.20
    mem_util: float = 0.30
    throughput_mbps: float = 80.0

    # Fault state
    fault_overload: float = 0.0
    fault_latency_spike: float = 0.0

    def update(self, active_sessions: float, compute_saturation: float = 0.0) -> None:
        # Request rate tracks edge sessions
        target_rps = active_sessions * 0.4
        self.request_rate = 0.9 * self.request_rate + 0.1 * target_rps + random.gauss(0, 3)
        self.request_rate = max(1.0, self.request_rate)

        # Active connections
        self.active_connections = self.request_rate * 0.8 + random.gauss(0, 5)
        self.active_connections = max(0.0, self.active_connections)

        # Throughput (approx 400 KB per request)
        self.throughput_mbps = self.request_rate * 0.4 * 8 / 1000 + random.gauss(0, 1)
        self.throughput_mbps = max(0.0, self.throughput_mbps)

        # Response time: baseline 5ms, rises with load and compute saturation
        load_factor = self.request_rate / 500.0  # normalise to 500 rps capacity
        self.response_time_ms = (
            5.0
            + load_factor * 20.0
            + compute_saturation * 30.0
            + self.fault_latency_spike * 50.0
            + self.fault_overload * 15.0
            + random.gauss(0, 0.5)
        )
        self.response_time_ms = max(1.0, self.response_time_ms)

        # Error rate rises with overload
        base_err = max(0.0, load_factor - 0.8) * 0.05
        self.error_rate = min(1.0, base_err + self.fault_overload * 0.1 + random.gauss(0, 0.0005))
        self.error_rate = max(0.0, self.error_rate)

        self.cpu_util = min(1.0, load_factor * 0.6 + self.fault_overload * 0.25 + random.gauss(0, 0.01))
        self.mem_util = min(1.0, 0.25 + load_factor * 0.4 + random.gauss(0, 0.005))

    def kpis(self) -> Dict[str, float]:
        return {
            "requestRateRps": round(self.request_rate, 1),
            "activeConnections": round(self.active_connections),
            "responseTimeMs": round(self.response_time_ms, 2),
            "errorRate": round(self.error_rate, 4),
            "throughputMbps": round(self.throughput_mbps, 2),
            "cpuUtilPct": round(self.cpu_util * 100, 1),
            "memUtilPct": round(self.mem_util * 100, 1),
        }
