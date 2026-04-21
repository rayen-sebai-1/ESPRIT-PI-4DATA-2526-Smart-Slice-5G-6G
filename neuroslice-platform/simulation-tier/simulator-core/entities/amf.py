"""
simulator-core/entities/amf.py
AMF (Access and Mobility Management Function) stateful entity.

Internal state drives KPI computation — no random independent values.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AMFState:
    # Capacity
    max_ues: int = 10_000
    max_registrations_per_sec: float = 500.0

    # Dynamic state — these are the "latent" variables that drive KPIs
    active_ues: float = 1000.0
    registration_queue: float = 0.0       # pending registrations
    signaling_load: float = 0.2           # 0–1  normalised load
    cpu_util: float = 0.2
    mem_util: float = 0.3
    error_rate: float = 0.005             # fraction of registrations that fail

    # Fault state flags (injected by fault-engine via Redis)
    fault_degradation: float = 0.0       # 0–1 additional error multiplier
    fault_cpu_spike: float = 0.0
    _smoothed_ue_delta: float = 0.0

    def apply_traffic_pattern(self, hour: float, traffic_modifier: float = 1.0) -> None:
        """
        Shape active UE count with a smooth daily sinusoidal pattern.
        Peak around hour 13, trough around hour 4.
        """
        peak = 0.5 * (1.0 - math.cos(2.0 * math.pi * (hour - 4) / 24))
        target_ues = self.max_ues * 0.1 + self.max_ues * 0.6 * peak * traffic_modifier
        # Smooth approach to target (inertia)
        delta = (target_ues - self.active_ues) * 0.05
        self._smoothed_ue_delta = 0.8 * self._smoothed_ue_delta + 0.2 * delta
        self.active_ues = max(50.0, self.active_ues + self._smoothed_ue_delta)
        self.active_ues += random.gauss(0, 20)
        self.active_ues = max(50.0, min(self.active_ues, self.max_ues * 1.05))

    def update(self, hour: float, traffic_modifier: float = 1.0) -> None:
        """One simulation tick — update all latent state variables."""
        self.apply_traffic_pattern(hour, traffic_modifier)

        # Registration queue grows with UE count
        arrival_rate = self.active_ues * 0.01  # ~1% churn/tick
        service_rate = self.max_registrations_per_sec * (1.0 - self.fault_degradation)
        self.registration_queue = max(0.0, self.registration_queue + arrival_rate - service_rate * 0.1)
        self.registration_queue = min(self.registration_queue, 5000)

        # Signaling load is proportional to UE count and queue
        load_from_ues = self.active_ues / self.max_ues
        load_from_queue = min(1.0, self.registration_queue / 1000.0)
        target_load = min(1.0, load_from_ues * 0.6 + load_from_queue * 0.4)
        self.signaling_load = 0.85 * self.signaling_load + 0.15 * target_load

        # CPU follows signaling load + fault spikes
        self.cpu_util = min(1.0, self.signaling_load * 0.7 + self.fault_cpu_spike + random.gauss(0, 0.01))
        self.mem_util = min(1.0, 0.25 + self.signaling_load * 0.45 + random.gauss(0, 0.005))

        # Error rate increases with overload and fault degradation
        base_error = 0.001 + max(0.0, self.signaling_load - 0.7) * 0.05
        self.error_rate = min(1.0, base_error * (1.0 + self.fault_degradation * 10))

    def kpis(self) -> Dict[str, float]:
        """Expose observable KPIs (what the VES/NETCONF adapter would report)."""
        reg_rate = self.max_registrations_per_sec * (1.0 - self.fault_degradation)
        success_rate = max(0.0, 1.0 - self.error_rate)
        latency_ms = 10.0 + self.registration_queue * 0.02 + random.gauss(0, 0.5)
        return {
            "activeUeCount": round(self.active_ues),
            "registrationSuccessRate": round(success_rate, 4),
            "registrationFailureRate": round(self.error_rate, 4),
            "registrationRatePps": round(reg_rate, 1),
            "signalingLoadPct": round(self.signaling_load * 100, 1),
            "pduSessionLatencyMs": round(max(1.0, latency_ms), 1),
            "cpuUtilPct": round(self.cpu_util * 100, 1),
            "memUtilPct": round(self.mem_util * 100, 1),
            "registrationQueueLen": round(self.registration_queue),
        }
