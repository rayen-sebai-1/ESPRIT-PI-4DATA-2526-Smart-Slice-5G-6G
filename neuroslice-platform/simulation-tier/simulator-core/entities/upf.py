"""
simulator-core/entities/upf.py
Central UPF (User Plane Function) stateful entity.

Core UPF handles all traffic not broken out at the edge.
KPIs depend on active sessions, slice misrouting (extra traffic),
and upstream RAN congestion.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict


@dataclass
class UPFState:
    """Central UPF — handles eMBB + misrouted URLLC traffic."""

    upf_id: str = "core-upf-01"
    max_throughput_gbps: float = 40.0     # capacity
    max_tunnels: int = 50_000

    # Latent state
    dl_throughput_gbps: float = 2.0
    ul_throughput_gbps: float = 0.8
    active_tunnels: int = 2000
    queue_depth: float = 0.0              # 0–1 normalised
    forwarding_latency_ms: float = 0.5
    packet_loss_pct: float = 0.0
    cpu_util: float = 0.15
    mem_util: float = 0.25

    # Misrouting — extra load from incorrectly placed URLLC traffic
    misrouting_extra_load: float = 0.0   # Gbps added by misrouted slices

    # Fault state
    fault_overload: float = 0.0          # 0–1 additional congestion
    fault_packet_loss: float = 0.0       # additional PL

    def update(self, active_sessions: float, ran_congestion: float = 0.0) -> None:
        """
        Throughput scales with sessions.
        Misrouted traffic and RAN congestion add extra load.
        """
        base_dl = active_sessions * 0.0005  # 500 Kbps average per session
        base_ul = base_dl * 0.4
        ran_multiplier = 1.0 + ran_congestion * 0.3  # RAN congestion spills to core

        total_dl = min(
            self.max_throughput_gbps * 0.95,
            (base_dl + self.misrouting_extra_load) * ran_multiplier + random.gauss(0, 0.05),
        )
        total_ul = min(self.max_throughput_gbps * 0.95, base_ul * ran_multiplier + random.gauss(0, 0.02))

        self.dl_throughput_gbps = max(0.0, 0.9 * self.dl_throughput_gbps + 0.1 * total_dl)
        self.ul_throughput_gbps = max(0.0, 0.9 * self.ul_throughput_gbps + 0.1 * total_ul)

        # Tunnels scale with sessions
        target_tunnels = int(active_sessions * 1.1)
        self.active_tunnels = max(0, min(self.max_tunnels, target_tunnels))

        # Queue depth — normalised utilisation
        utilisation = (self.dl_throughput_gbps + self.ul_throughput_gbps) / self.max_throughput_gbps
        self.queue_depth = min(1.0, utilisation * 0.8 + self.fault_overload + random.gauss(0, 0.01))

        # Latency rises sharply when queue > 0.7
        if self.queue_depth < 0.7:
            self.forwarding_latency_ms = 0.5 + self.queue_depth * 1.0
        else:
            self.forwarding_latency_ms = 0.5 + self.queue_depth * 5.0
        self.forwarding_latency_ms += random.gauss(0, 0.05)
        self.forwarding_latency_ms = max(0.1, self.forwarding_latency_ms)

        # Packet loss: negligible until queue > 0.85
        base_pl = max(0.0, (self.queue_depth - 0.85) * 10.0)
        self.packet_loss_pct = min(100.0, base_pl + self.fault_packet_loss * 100)
        self.packet_loss_pct = max(0.0, self.packet_loss_pct + random.gauss(0, 0.05))

        # CPU/mem
        self.cpu_util = min(1.0, utilisation * 0.6 + self.fault_overload * 0.3 + random.gauss(0, 0.01))
        self.mem_util = min(1.0, 0.2 + utilisation * 0.45 + random.gauss(0, 0.005))

    def kpis(self) -> Dict[str, float]:
        return {
            "dlThroughputGbps": round(self.dl_throughput_gbps, 3),
            "ulThroughputGbps": round(self.ul_throughput_gbps, 3),
            "activeTunnels": self.active_tunnels,
            "queueDepthPct": round(self.queue_depth * 100, 1),
            "forwardingLatencyMs": round(self.forwarding_latency_ms, 2),
            "packetLossPct": round(self.packet_loss_pct, 3),
            "cpuUtilPct": round(self.cpu_util * 100, 1),
            "memUtilPct": round(self.mem_util * 100, 1),
        }
