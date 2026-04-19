"""
simulator-ran/entities/cell.py
Cell (NR cell sector) stateful entity.

Each cell contains multiple slices. Cell-level KPIs are aggregated
from slice KPIs plus radio layer parameters (RSRP, SINR, CQI, BLER).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List

from entities.slice_state import SliceState


@dataclass
class CellState:
    cell_id: str
    gnb_id: str
    total_rbs: int = 106        # 100 MHz NR bandwidth
    max_ues: int = 200

    # Radio state
    rsrp_dbm: float = -80.0
    rsrq_db: float = -10.0
    sinr_db: float = 15.0
    cqi: float = 10.0           # 0–15
    bler_pct: float = 1.0       # block error rate %

    # Mobility
    handover_attempts: int = 0
    handover_successes: int = 0

    # RRC
    rrc_attempts: int = 0
    rrc_successes: int = 0

    # Slices hosted by this cell
    slices: List[SliceState] = field(default_factory=list)

    # Fault state
    fault_congestion: float = 0.0
    fault_rfs_degradation: float = 0.0  # RF degradation factor

    def total_ues(self) -> int:
        return sum(s.ue_count for s in self.slices)

    def update(self, hour: float, total_ues_base: int, congestion_override: float = 0.0) -> None:
        congestion = max(self.fault_congestion, congestion_override)

        # Update all slices
        for sl in self.slices:
            sl.fault_congestion = congestion
            sl.update(hour, total_ues_base)

        ues = self.total_ues()
        load = min(1.0, ues / self.max_ues)

        # Radio parameters — load and RF degradation affect quality
        rf_deg = self.fault_rfs_degradation
        self.rsrp_dbm = -80.0 - rf_deg * 10.0 + random.gauss(0, 1.0)
        self.rsrq_db = -10.0 - load * 4.0 - rf_deg * 5.0 + random.gauss(0, 0.5)
        self.sinr_db = max(0.0, 20.0 - load * 8.0 - rf_deg * 6.0 + random.gauss(0, 0.5))
        # CQI mapped from SINR (simplified)
        self.cqi = max(1.0, min(15.0, self.sinr_db / 2.0 + random.gauss(0, 0.3)))

        # BLER rises with degraded CQI and high load
        self.bler_pct = max(0.0, 1.0 + (15.0 - self.cqi) * 0.5 + load * 2.0 + random.gauss(0, 0.1))

        # Handovers scale with UE count and congestion (congestion triggers HOs)
        ho_rate = ues * 0.002 * (1.0 + congestion * 3.0)
        self.handover_attempts = max(0, int(ho_rate + random.gauss(0, 1)))
        ho_success_rate = max(0.70, 0.99 - congestion * 0.25 - rf_deg * 0.10)
        self.handover_successes = int(self.handover_attempts * ho_success_rate)

        # RRC setup
        rrc_rate = ues * 0.01
        self.rrc_attempts = max(0, int(rrc_rate + random.gauss(0, 1)))
        rrc_success_rate = max(0.85, 0.999 - congestion * 0.12)
        self.rrc_successes = int(self.rrc_attempts * rrc_success_rate)

    def aggregate_rb_utilization(self) -> float:
        total_rb_pct = sum(s.rb_utilization_pct * s.profile.max_rb_pct for s in self.slices)
        return min(100.0, total_rb_pct)

    @property
    def congestion_score(self) -> float:
        if not self.slices:
            return 0.0
        return max(s.congestion_score for s in self.slices)

    @property
    def health_score(self) -> float:
        return 1.0 - self.congestion_score

    @property
    def handover_success_rate(self) -> float:
        if self.handover_attempts == 0:
            return 1.0
        return self.handover_successes / self.handover_attempts

    @property
    def rrc_success_rate(self) -> float:
        if self.rrc_attempts == 0:
            return 1.0
        return self.rrc_successes / self.rrc_attempts

    def kpis(self) -> Dict[str, float]:
        return {
            "ueCount": self.total_ues(),
            "rbUtilizationPct": round(self.aggregate_rb_utilization(), 1),
            "rsrpDbm": round(self.rsrp_dbm, 1),
            "rsrqDb": round(self.rsrq_db, 1),
            "sinrDb": round(self.sinr_db, 1),
            "cqi": round(self.cqi, 1),
            "blerPct": round(self.bler_pct, 2),
            "handoverSuccessRate": round(self.handover_success_rate, 4),
            "rrcSetupSuccessRate": round(self.rrc_success_rate, 4),
            "handoverAttempts": self.handover_attempts,
            "rrcAttempts": self.rrc_attempts,
        }
