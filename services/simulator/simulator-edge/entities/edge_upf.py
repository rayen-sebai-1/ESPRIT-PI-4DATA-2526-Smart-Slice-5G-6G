"""
simulator-edge/entities/edge_upf.py
Edge UPF stateful entity.

Handles local traffic breakout for URLLC and eMBB edge slices.
Affected by slice misrouting (loss of traffic) and overload.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict


@dataclass
class EdgeUPFState:
    upf_id: str = "edge-upf-01"
    max_throughput_gbps: float = 10.0

    # Latent state
    dl_throughput_gbps: float = 0.5
    ul_throughput_gbps: float = 0.2
    active_sessions: float = 500.0
    forwarding_latency_ms: float = 1.0
    packet_loss_pct: float = 0.0
    local_breakout_ratio: float = 0.85   # fraction of edge traffic not going to core
    cpu_util: float = 0.15
    mem_util: float = 0.20

    # Misrouting — when active, traffic is sent to central UPF instead
    # local_breakout_ratio drops, dl_throughput drops proportionally
    misrouting_ratio: float = 0.0        # 0=normal, 1=all traffic misrouted

    # Fault state
    fault_overload: float = 0.0
    fault_packet_loss: float = 0.0

    def update(self, active_sessions: float, ran_congestion: float = 0.0) -> None:
        self.active_sessions = max(0.0, active_sessions + random.gauss(0, 5))

        # Misrouting reduces local throughput
        effective_sessions = self.active_sessions * (1.0 - self.misrouting_ratio)
        base_dl = effective_sessions * 0.0008  # 800 Kbps avg per edge session
        base_ul = base_dl * 0.35

        total_dl = min(self.max_throughput_gbps * 0.9, base_dl + random.gauss(0, 0.02))
        total_ul = min(self.max_throughput_gbps * 0.9, base_ul + random.gauss(0, 0.01))
        self.dl_throughput_gbps = max(0.0, 0.9 * self.dl_throughput_gbps + 0.1 * total_dl)
        self.ul_throughput_gbps = max(0.0, 0.9 * self.ul_throughput_gbps + 0.1 * total_ul)

        util = (self.dl_throughput_gbps + self.ul_throughput_gbps) / self.max_throughput_gbps
        # Latency rises with util + ran congestion spillover
        self.forwarding_latency_ms = (
            1.0 + util * 3.0 + ran_congestion * 2.0 + self.fault_overload * 5.0 + random.gauss(0, 0.1)
        )
        self.forwarding_latency_ms = max(0.5, self.forwarding_latency_ms)

        overload_pl = max(0.0, (util + self.fault_overload - 0.85) * 8.0)
        self.packet_loss_pct = max(0.0, overload_pl + self.fault_packet_loss * 100 + random.gauss(0, 0.02))

        self.local_breakout_ratio = max(0.0, 0.85 - self.misrouting_ratio * 0.85)

        self.cpu_util = min(1.0, util * 0.55 + self.fault_overload * 0.35 + random.gauss(0, 0.01))
        self.mem_util = min(1.0, 0.18 + util * 0.4 + random.gauss(0, 0.005))

    def kpis(self) -> Dict[str, float]:
        return {
            "dlThroughputGbps": round(self.dl_throughput_gbps, 3),
            "ulThroughputGbps": round(self.ul_throughput_gbps, 3),
            "activeSessions": round(self.active_sessions),
            "forwardingLatencyMs": round(self.forwarding_latency_ms, 2),
            "packetLossPct": round(self.packet_loss_pct, 3),
            "localBreakoutRatio": round(self.local_breakout_ratio, 3),
            "cpuUtilPct": round(self.cpu_util * 100, 1),
            "memUtilPct": round(self.mem_util * 100, 1),
        }
