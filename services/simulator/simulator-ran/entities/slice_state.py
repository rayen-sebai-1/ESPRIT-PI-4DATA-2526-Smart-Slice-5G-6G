"""
simulator-ran/entities/slice_state.py
Per-slice state tracker for eMBB, URLLC, and mMTC slices.

Each slice has its own RB allocation, traffic profile, and QoS constraints.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class SliceProfile:
    """Static QoS profile for a slice type."""
    name: str
    max_rb_pct: float       # max % of RBs allocated
    target_latency_ms: float
    target_throughput_mbps: float
    # Traffic shape: fraction of peak load at different times
    peak_hour: float        # hour of day with peak demand
    traffic_variance: float

    # SLA thresholds
    sla_latency_ms: float
    sla_packet_loss_pct: float
    sla_throughput_mbps: float


SLICE_PROFILES = {
    "eMBB": SliceProfile(
        name="eMBB",
        max_rb_pct=0.60,
        target_latency_ms=20.0,
        target_throughput_mbps=300.0,
        peak_hour=13.0,
        traffic_variance=0.15,
        sla_latency_ms=50.0,
        sla_packet_loss_pct=2.0,
        sla_throughput_mbps=100.0,
    ),
    "URLLC": SliceProfile(
        name="URLLC",
        max_rb_pct=0.20,
        target_latency_ms=1.0,
        target_throughput_mbps=50.0,
        peak_hour=10.0,
        traffic_variance=0.05,
        sla_latency_ms=5.0,
        sla_packet_loss_pct=0.01,
        sla_throughput_mbps=20.0,
    ),
    "mMTC": SliceProfile(
        name="mMTC",
        max_rb_pct=0.20,
        target_latency_ms=100.0,
        target_throughput_mbps=10.0,
        peak_hour=9.0,
        traffic_variance=0.20,
        sla_latency_ms=500.0,
        sla_packet_loss_pct=5.0,
        sla_throughput_mbps=1.0,
    ),
}


@dataclass
class SliceState:
    """Dynamic KPI state for a slice instance."""
    slice_id: str
    slice_type: str
    profile: SliceProfile = field(init=False)

    # Dynamic state
    rb_utilization_pct: float = 0.0
    dl_throughput_mbps: float = 0.0
    ul_throughput_mbps: float = 0.0
    latency_ms: float = 0.0
    packet_loss_pct: float = 0.0
    ue_count: int = 0

    # Misrouting (for URLLC)
    expected_upf: str = "edge-upf-01"
    actual_upf: str = "edge-upf-01"
    qos_profile_expected: str = ""
    qos_profile_actual: str = ""
    misrouting_active: bool = False

    # Fault/cross-domain influence
    fault_congestion: float = 0.0
    fault_latency_spike: float = 0.0
    fault_packet_loss: float = 0.0

    def __post_init__(self) -> None:
        self.profile = SLICE_PROFILES[self.slice_type]
        self.qos_profile_expected = self.slice_type.lower()
        self.qos_profile_actual = self.slice_type.lower()

    def update(self, hour: float, total_ues: int, congestion_override: float = 0.0) -> None:
        profile = self.profile
        # Traffic pattern: sinusoidal around peak_hour
        peak_dist = abs(hour - profile.peak_hour)
        if peak_dist > 12:
            peak_dist = 24 - peak_dist
        load_factor = max(0.05, 1.0 - (peak_dist / 12.0) ** 1.5)
        load_factor += random.gauss(0, profile.traffic_variance)
        load_factor = max(0.02, min(1.0, load_factor))

        # Slice UE allocation
        ue_share = {"eMBB": 0.60, "URLLC": 0.05, "mMTC": 0.35}
        self.ue_count = max(1, int(total_ues * ue_share.get(self.slice_type, 0.3) * load_factor))

        # RB utilisation — base + congestion
        base_rb = self.ue_count / 200.0  # 200 UEs = 100% RB util
        congestion = max(congestion_override, self.fault_congestion)
        self.rb_utilization_pct = min(100.0, base_rb * 100.0 * (1.0 + congestion * 0.5))
        self.rb_utilization_pct = max(1.0, self.rb_utilization_pct + random.gauss(0, 1.0))

        # Throughput from RB utilisation
        rb_eff = self.rb_utilization_pct / 100.0
        self.dl_throughput_mbps = (
            profile.target_throughput_mbps * rb_eff * (1.0 - self.fault_packet_loss) + random.gauss(0, 2)
        )
        self.dl_throughput_mbps = max(0.0, self.dl_throughput_mbps)
        self.ul_throughput_mbps = self.dl_throughput_mbps * 0.35 + random.gauss(0, 0.5)
        self.ul_throughput_mbps = max(0.0, self.ul_throughput_mbps)

        # Latency — rises with RB utilisation and congestion
        if self.rb_utilization_pct < 70:
            self.latency_ms = profile.target_latency_ms * (1.0 + rb_eff * 0.3)
        else:
            # Exponential rise above 70%
            excess = (self.rb_utilization_pct - 70) / 30.0
            self.latency_ms = profile.target_latency_ms * (1.0 + excess ** 2 * 3.0)
        # Misrouting adds extra latency for URLLC
        if self.misrouting_active and self.slice_type == "URLLC":
            self.latency_ms += 15.0  # extra hop to core UPF
            self.actual_upf = "core-upf-01"
            self.qos_profile_actual = "embb"  # wrong QoS class
        else:
            self.actual_upf = self.expected_upf
            self.qos_profile_actual = self.qos_profile_expected

        self.latency_ms += self.fault_latency_spike * 20.0 + random.gauss(0, 0.5)
        self.latency_ms = max(0.1, self.latency_ms)

        # Packet loss — negligible until congestion + overload
        rb_pl = max(0.0, (self.rb_utilization_pct - 85.0) / 15.0) * 3.0
        misrouting_pl = 0.2 if self.misrouting_active and self.slice_type == "URLLC" else 0.0
        self.packet_loss_pct = max(
            0.0,
            rb_pl + misrouting_pl + self.fault_packet_loss * 100 + random.gauss(0, 0.05),
        )

    def sla_met(self) -> bool:
        p = self.profile
        return (
            self.latency_ms <= p.sla_latency_ms
            and self.packet_loss_pct <= p.sla_packet_loss_pct
            and self.dl_throughput_mbps >= p.sla_throughput_mbps
        )

    @property
    def congestion_score(self) -> float:
        return min(1.0, self.rb_utilization_pct / 100.0 * 0.7 + self.packet_loss_pct / 10.0 * 0.3)

    @property
    def health_score(self) -> float:
        return 1.0 - self.congestion_score

    @property
    def misrouting_score(self) -> float:
        if not self.misrouting_active or self.slice_type != "URLLC":
            return 0.0
        return min(1.0, (self.latency_ms - self.profile.target_latency_ms) / 20.0)

    def kpis(self) -> Dict[str, float]:
        return {
            "rbUtilizationPct": round(self.rb_utilization_pct, 1),
            "dlThroughputMbps": round(self.dl_throughput_mbps, 1),
            "ulThroughputMbps": round(self.ul_throughput_mbps, 1),
            "latencyMs": round(self.latency_ms, 2),
            "packetLossPct": round(self.packet_loss_pct, 3),
            "ueCount": self.ue_count,
        }
