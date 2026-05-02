"""
simulator-ran/engine.py
SimPy tick engine for the RAN domain.
Manages 2 gNBs × 2 cells each × 3 slices per cell = 12 slice instances.
Publishes telemetry via VES adapter and RAN congestion score to Redis.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import sys
from datetime import datetime, timezone
from typing import List

import httpx
import redis
import simpy

sys.path.insert(0, "/shared")

from shared.config import get_config
from shared.models import Domain, EntityType, Protocol, RawVesEvent
from shared.redis_client import get_redis

from entities.gnb import GNBState
from entities.cell import CellState
from entities.slice_state import SliceState

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

cfg = get_config()
SITE_ID = cfg.site_id
VES_ADAPTER_URL = cfg.ves_adapter_url


def build_ran_topology() -> List[GNBState]:
    """
    Create 2 gNBs, each with 2 cells, each cell hosting 3 slices.
    Returns the configured gNB list.
    """
    gnbs = []
    for gi in range(1, 3):
        gnb = GNBState(gnb_id=f"gnb-{gi:02d}")
        for ci in range(1, 3):
            cell_id = f"cell-{gi:02d}-{ci:02d}"
            cell = CellState(cell_id=cell_id, gnb_id=gnb.gnb_id)
            # Attach slices
            cell.slices = [
                SliceState(
                    slice_id=f"slice-embb-{gi:02d}-{ci:02d}",
                    slice_type="eMBB",
                    expected_upf="edge-upf-01",
                ),
                SliceState(
                    slice_id=f"slice-urllc-{gi:02d}-{ci:02d}",
                    slice_type="URLLC",
                    expected_upf="edge-upf-01",
                ),
                SliceState(
                    slice_id=f"slice-mmtc-{gi:02d}-{ci:02d}",
                    slice_type="mMTC",
                    expected_upf="core-upf-01",
                ),
            ]
            gnb.cells.append(cell)
        gnbs.append(gnb)
    return gnbs


class RANSimulationEngine:
    def __init__(self) -> None:
        self.env = simpy.Environment()
        self.gnbs = build_ran_topology()
        self.redis = None
        self.http_client = None
        self.current_scenario = "normal_day"
        self.traffic_modifier = 1.0

    def _sim_hour(self) -> float:
        sim_seconds = self.env.now * cfg.sim_speed
        return (sim_seconds / 3600) % 24

    def _load_fault_state(self) -> None:
        if not self.redis:
            return
        try:
            raw = self.redis.hgetall("faults:active")
            ran_congestion = 0.0
            misrouting = False
            rf_deg = 0.0
            pl = 0.0
            latency_spike = 0.0
            for fv in (raw or {}).values():
                fault = json.loads(fv)
                ft = fault.get("fault_type", "")
                impacts = fault.get("kpi_impacts", {})
                if ft == "ran_congestion":
                    ran_congestion = max(ran_congestion, impacts.get("congestion", 0.5))
                if ft == "slice_misrouting":
                    misrouting = True
                if ft == "packet_loss_spike":
                    pl = max(pl, impacts.get("packet_loss", 0.05))
                if ft == "latency_spike":
                    latency_spike = max(latency_spike, impacts.get("latency_mult", 2.0) - 1.0)
                self.current_scenario = fault.get("scenario_id", self.current_scenario)
                self.traffic_modifier = fault.get("traffic_modifier", self.traffic_modifier)

            for gnb in self.gnbs:
                gnb.fault_congestion = ran_congestion
                gnb.fault_rf_degradation = rf_deg
                for cell in gnb.cells:
                    for sl in cell.slices:
                        sl.fault_packet_loss = pl
                        sl.fault_latency_spike = latency_spike
                        if sl.slice_type == "URLLC":
                            sl.misrouting_active = misrouting
        except Exception as exc:
            logger.warning("Fault load error: %s", exc)

    def _build_slice_ves(self, gnb_id: str, cell_id: str, sl: SliceState) -> dict:
        return RawVesEvent(
            source="simulator-ran",
            domain=Domain.RAN.value,
            entity_id=sl.slice_id,
            entity_type=EntityType.CELL.value,
            site_id=SITE_ID,
            node_id=gnb_id,
            slice_id=sl.slice_id,
            slice_type=sl.slice_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            kpis=sl.kpis(),
            internal={
                "expectedUpf": sl.expected_upf,
                "actualUpf": sl.actual_upf,
                "qosExpected": sl.qos_profile_expected,
                "qosActual": sl.qos_profile_actual,
                "misroutingActive": sl.misrouting_active,
                "slaMet": sl.sla_met(),
                "congestionScore": sl.congestion_score,
                "healthScore": sl.health_score,
                "misroutingScore": sl.misrouting_score,
            },
            scenario_id=self.current_scenario,
        ).model_dump()

    def _build_cell_ves(self, gnb_id: str, cell: CellState) -> dict:
        return RawVesEvent(
            source="simulator-ran",
            domain=Domain.RAN.value,
            entity_id=cell.cell_id,
            entity_type=EntityType.CELL.value,
            site_id=SITE_ID,
            node_id=gnb_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            kpis=cell.kpis(),
            internal={},
            scenario_id=self.current_scenario,
        ).model_dump()

    @staticmethod
    def _as_float(value, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    async def _emit(self, events: list) -> None:
        if not self.http_client:
            return
        for ev in events:
            try:
                await self.http_client.post(f"{VES_ADAPTER_URL}/events", json=ev, timeout=3.0)
            except Exception as exc:
                logger.debug("VES emit error: %s", exc)

    def tick(self, env: simpy.Environment):
        while True:
            hour = self._sim_hour()
            self._load_fault_state()
            qos_boost = 0.0
            reroute_bias = 0.0

            # Base UEs from core AMF (Redis)
            base_ues = 150
            try:
                if self.redis:
                    v = self.redis.get("core:active_ues")
                    if v:
                        base_ues = max(10, int(float(v) / 4))  # distribute across cells
                    qos_boost = max(0.0, min(1.0, self._as_float(self.redis.get("control:sim:qos_boost"))))
                    reroute_bias = max(
                        0.0,
                        min(1.0, self._as_float(self.redis.get("control:sim:reroute_bias"))),
                    )
            except Exception:
                pass

            events = []
            max_congestion = 0.0
            for gnb in self.gnbs:
                gnb.update(hour, base_ues)
                max_congestion = max(max_congestion, gnb.congestion_score)

                for cell in gnb.cells:
                    for sl in cell.slices:
                        slice_reroute_bias = reroute_bias
                        if self.redis and sl.slice_id:
                            slice_reroute_bias = max(
                                slice_reroute_bias,
                                max(
                                    0.0,
                                    min(
                                        1.0,
                                        self._as_float(
                                            self.redis.get(f"control:sim:reroute_bias:{sl.slice_id}")
                                        ),
                                    ),
                                ),
                            )

                        if qos_boost > 0.0:
                            qos_factor = 1.0 - min(0.6, qos_boost)
                            sl.rb_utilization_pct = max(0.0, sl.rb_utilization_pct * qos_factor)
                            sl.latency_ms = max(0.1, sl.latency_ms * (1.0 - min(0.5, qos_boost)))
                            sl.packet_loss_pct = max(0.0, sl.packet_loss_pct * (1.0 - min(0.7, qos_boost)))

                        if slice_reroute_bias > 0.0:
                            reroute_factor = 1.0 - min(0.6, slice_reroute_bias)
                            sl.ue_count = max(1, int(sl.ue_count * reroute_factor))
                            sl.rb_utilization_pct = max(0.0, sl.rb_utilization_pct * reroute_factor)
                            sl.latency_ms = max(0.1, sl.latency_ms * reroute_factor)
                            sl.packet_loss_pct = max(0.0, sl.packet_loss_pct * reroute_factor)
                            if sl.slice_type == "URLLC":
                                sl.misrouting_active = False
                                sl.actual_upf = sl.expected_upf
                                sl.qos_profile_actual = sl.qos_profile_expected

                        max_congestion = max(max_congestion, sl.congestion_score)
                        events.append(self._build_slice_ves(gnb.gnb_id, cell.cell_id, sl))
                    events.append(self._build_cell_ves(gnb.gnb_id, cell))
                events.append(self._build_cell_ves(gnb.gnb_id, gnb.cells[0]))  # gNB-level summary

            # Publish RAN congestion score for other domains to consume
            try:
                if self.redis:
                    active_ues_total = sum(c.total_ues() for g in self.gnbs for c in g.cells)
                    self.redis.set("ran:congestion_score", max_congestion)
                    self.redis.set("core:active_ues", active_ues_total)
                    # Backward-compatible alias used by simulator-edge.
                    self.redis.set("core:active_sessions", active_ues_total)
                    self.redis.set("ran:qos_boost", qos_boost)
                    self.redis.set("ran:reroute_bias", reroute_bias)
            except Exception:
                pass

            asyncio.create_task(self._emit(events))

            logger.info(
                "[SIM-RAN tick=%.0f h=%.1f] congestion=%.3f events=%d",
                env.now, hour, max_congestion, len(events),
            )

            yield env.timeout(1)

    async def run(self) -> None:
        for attempt in range(20):
            try:
                self.redis = get_redis()
                self.redis.ping()
                logger.info("Connected to Redis")
                break
            except Exception as exc:
                logger.warning("Waiting for Redis (%d/20): %s", attempt + 1, exc)
                await asyncio.sleep(3)

        self.http_client = httpx.AsyncClient()
        self.env.process(self.tick(self.env))

        while True:
            self.env.step()
            await asyncio.sleep(cfg.tick_interval_sec)


async def main() -> None:
    engine = RANSimulationEngine()
    await engine.run()


if __name__ == "__main__":
    asyncio.run(main())
