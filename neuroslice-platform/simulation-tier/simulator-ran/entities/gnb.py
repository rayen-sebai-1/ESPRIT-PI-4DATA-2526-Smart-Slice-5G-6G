"""
simulator-ran/entities/gnb.py
gNB (Next-Generation NodeB) stateful entity.

Each gNB manages multiple cells.
gNB-level congestion score is published to Redis for cross-domain use.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from entities.cell import CellState
from entities.slice_state import SliceState


@dataclass
class GNBState:
    gnb_id: str
    backhaul_capacity_gbps: float = 10.0

    cells: List[CellState] = field(default_factory=list)

    # Computed
    backhaul_utilization: float = 0.0
    fault_congestion: float = 0.0
    fault_rf_degradation: float = 0.0

    def update(self, hour: float, base_ues_per_cell: int = 150) -> None:
        for cell in self.cells:
            cell.fault_congestion = self.fault_congestion
            cell.fault_rfs_degradation = self.fault_rf_degradation
            cell.update(hour, base_ues_per_cell, self.fault_congestion)

        # Backhaul = aggregate DL throughput across all cells and slices
        total_dl_gbps = sum(
            s.dl_throughput_mbps / 1000.0
            for cell in self.cells
            for s in cell.slices
        )
        self.backhaul_utilization = min(1.0, total_dl_gbps / self.backhaul_capacity_gbps)

    @property
    def congestion_score(self) -> float:
        if not self.cells:
            return 0.0
        return max(c.congestion_score for c in self.cells)

    def kpis(self) -> Dict[str, float]:
        total_ues = sum(c.total_ues() for c in self.cells)
        return {
            "totalUeCount": total_ues,
            "cellCount": len(self.cells),
            "backhaulUtilizationPct": round(self.backhaul_utilization * 100, 1),
            "gnbCongestionScore": round(self.congestion_score, 3),
        }
