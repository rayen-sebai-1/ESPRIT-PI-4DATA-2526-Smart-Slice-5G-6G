"""
simulator-core/entities/smf.py
SMF (Session Management Function) stateful entity.

SMF session state depends on AMF UE count and UPF throughput.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict


@dataclass
class SMFState:
    max_sessions: int = 20_000
    max_pdu_rate: float = 2000.0   # sessions/sec capacity

    # Latent state
    active_sessions: float = 2000.0
    pdu_setup_queue: float = 0.0
    setup_latency_ms: float = 5.0
    cpu_util: float = 0.15
    mem_util: float = 0.25
    pdu_success_rate: float = 0.999

    # Fault state
    fault_degradation: float = 0.0

    def update(self, active_ues: float, traffic_modifier: float = 1.0) -> None:
        """
        Sessions scale with active UEs.
        Each UE on average holds ~2–3 PDU sessions.
        """
        target_sessions = active_ues * 2.2 * traffic_modifier
        self.active_sessions = 0.9 * self.active_sessions + 0.1 * target_sessions
        self.active_sessions = max(0.0, min(self.active_sessions, self.max_sessions * 1.1))

        # Queue grows when session demand rises faster than capacity
        arrival = max(0.0, self.active_sessions - 2000) * 0.005
        service = self.max_pdu_rate * 0.1 * (1.0 - self.fault_degradation)
        self.pdu_setup_queue = max(0.0, self.pdu_setup_queue + arrival - service)
        self.pdu_setup_queue = min(self.pdu_setup_queue, 5000)

        # Latency scales with queue
        self.setup_latency_ms = 5.0 + self.pdu_setup_queue * 0.03 + random.gauss(0, 0.2)
        self.setup_latency_ms = max(1.0, self.setup_latency_ms)

        # CPU/mem driven by session count
        load = self.active_sessions / self.max_sessions
        self.cpu_util = min(1.0, load * 0.5 + self.fault_degradation * 0.3 + random.gauss(0, 0.01))
        self.mem_util = min(1.0, 0.2 + load * 0.4 + random.gauss(0, 0.005))

        # Success rate degrades under overload
        base_fail = max(0.0, load - 0.8) * 0.05
        fault_fail = self.fault_degradation * 0.1
        self.pdu_success_rate = max(0.0, 1.0 - base_fail - fault_fail)

    def kpis(self) -> Dict[str, float]:
        return {
            "activeSessions": round(self.active_sessions),
            "pduSessionSuccessRate": round(self.pdu_success_rate, 4),
            "pduSetupLatencyMs": round(self.setup_latency_ms, 2),
            "pduSetupQueueLen": round(self.pdu_setup_queue),
            "cpuUtilPct": round(self.cpu_util * 100, 1),
            "memUtilPct": round(self.mem_util * 100, 1),
        }
