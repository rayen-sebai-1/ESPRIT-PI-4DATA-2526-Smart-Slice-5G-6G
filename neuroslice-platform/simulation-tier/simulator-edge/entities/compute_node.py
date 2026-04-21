"""
simulator-edge/entities/compute_node.py
Edge Compute Node stateful entity.

Tracks vCPU, memory, and GPU (for AI inference) usage.
Saturation propagates to MEC app latency.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict


@dataclass
class ComputeNodeState:
    node_id: str = "edge-comp-01"
    vcpus: int = 32
    mem_gb: float = 128.0

    # Latent state
    cpu_util: float = 0.20
    mem_util: float = 0.30
    network_in_gbps: float = 0.2
    network_out_gbps: float = 0.4
    running_vnfs: int = 3
    saturation: float = 0.0  # composite stress score 0–1

    # Fault state
    fault_overload: float = 0.0

    def update(self, request_rate: float) -> None:
        # VNF load scales with requests
        load = request_rate / (self.vcpus * 20)  # ~20 rps per vCPU baseline
        target_cpu = min(1.0, load + self.fault_overload * 0.4)
        self.cpu_util = 0.85 * self.cpu_util + 0.15 * target_cpu + random.gauss(0, 0.01)
        self.cpu_util = max(0.0, min(1.0, self.cpu_util))

        self.mem_util = min(1.0, 0.25 + self.cpu_util * 0.5 + random.gauss(0, 0.005))

        self.network_in_gbps = request_rate * 0.0004 + random.gauss(0, 0.01)
        self.network_out_gbps = self.network_in_gbps * 2.0

        # Composite saturation score
        self.saturation = min(1.0, (self.cpu_util * 0.6 + self.mem_util * 0.4))

    @property
    def is_saturated(self) -> bool:
        return self.saturation > 0.85

    def kpis(self) -> Dict[str, float]:
        return {
            "cpuUtilPct": round(self.cpu_util * 100, 1),
            "memUtilPct": round(self.mem_util * 100, 1),
            "networkInGbps": round(self.network_in_gbps, 3),
            "networkOutGbps": round(self.network_out_gbps, 3),
            "runningVnfs": self.running_vnfs,
            "saturationScore": round(self.saturation, 3),
        }
