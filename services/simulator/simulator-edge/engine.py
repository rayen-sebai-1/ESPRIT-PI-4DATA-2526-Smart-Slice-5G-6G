"""
simulator-edge/engine.py
SimPy tick engine for the Edge domain.
Sends telemetry via NETCONF adapter.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone

import httpx
import redis
import simpy

sys.path.insert(0, "/shared")

from shared.config import get_config
from shared.models import Domain, EntityType, RawNetconfEvent
from shared.redis_client import get_redis

from entities.edge_upf import EdgeUPFState
from entities.mec_app import MECAppState
from entities.compute_node import ComputeNodeState

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)

cfg = get_config()
SITE_ID = cfg.site_id
NETCONF_ADAPTER_URL = cfg.netconf_adapter_url


class EdgeSimulationEngine:
    def __init__(self) -> None:
        self.env = simpy.Environment()
        self.edge_upf = EdgeUPFState()
        self.mec_app = MECAppState()
        self.compute = ComputeNodeState()
        self.redis = None
        self.http_client = None
        self.current_scenario = "normal_day"

    def _load_fault_state(self) -> None:
        if not self.redis:
            return
        try:
            raw = self.redis.hgetall("faults:active")
            overload = 0.0
            latency_spike = 0.0
            pl = 0.0
            misrouting = 0.0
            for fault_id, fv in (raw or {}).items():
                fault = json.loads(fv)
                ft = fault.get("fault_type", "")
                impacts = fault.get("kpi_impacts", {})
                if ft == "edge_overload":
                    overload = max(overload, impacts.get("overload", 0.4))
                if ft == "latency_spike":
                    latency_spike = max(latency_spike, impacts.get("latency_mult", 2.0) - 1.0)
                if ft == "packet_loss_spike":
                    pl = max(pl, impacts.get("packet_loss", 0.05))
                if ft == "slice_misrouting":
                    misrouting = max(misrouting, impacts.get("misrouting_ratio", 0.8))
                self.current_scenario = fault.get("scenario_id", self.current_scenario)

            self.edge_upf.fault_overload = overload
            self.edge_upf.fault_packet_loss = pl
            self.edge_upf.misrouting_ratio = misrouting
            self.mec_app.fault_overload = overload
            self.mec_app.fault_latency_spike = latency_spike
            self.compute.fault_overload = overload
        except Exception as exc:
            logger.warning("Fault load error: %s", exc)

    def _build_netconf_event(self, managed_element: str, data: dict) -> dict:
        return RawNetconfEvent(
            source="simulator-edge",
            managed_element=managed_element,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=data,
            scenario_id=self.current_scenario,
        ).model_dump()

    async def _emit(self, events: list) -> None:
        if not self.http_client:
            return
        for ev in events:
            try:
                await self.http_client.post(f"{NETCONF_ADAPTER_URL}/telemetry", json=ev, timeout=3.0)
            except Exception as exc:
                logger.debug("NETCONF emit error: %s", exc)

    def tick(self, env: simpy.Environment):
        while True:
            self._load_fault_state()

            # Get RAN congestion from Redis
            ran_congestion = 0.0
            edge_sessions = 500.0
            try:
                if self.redis:
                    v = self.redis.get("ran:congestion_score")
                    if v:
                        ran_congestion = float(v)
                    # Pull edge session count published by ran simulator
                    s = self.redis.get("core:active_sessions")
                    if s:
                        edge_sessions = float(s) * 0.15  # ~15% of sessions go to edge
            except Exception:
                pass

            # Causal update chain
            self.compute.update(self.mec_app.request_rate)
            self.mec_app.update(edge_sessions, self.compute.saturation)
            self.edge_upf.update(edge_sessions, ran_congestion)

            # Store state in Redis for cross-domain reference
            try:
                if self.redis:
                    self.redis.set("edge:saturation", self.compute.saturation)
                    self.redis.set("edge:misrouting_ratio", self.edge_upf.misrouting_ratio)
            except Exception:
                pass

            events = [
                self._build_netconf_event(
                    "edge-upf-01",
                    {
                        "upf": {**self.edge_upf.kpis(), "entityType": EntityType.EDGE_UPF.value},
                        "metadata": {"siteId": SITE_ID, "domain": Domain.EDGE.value},
                    },
                ),
                self._build_netconf_event(
                    "mec-app-01",
                    {
                        "app": {**self.mec_app.kpis(), "entityType": EntityType.MEC_APP.value},
                        "metadata": {"siteId": SITE_ID, "domain": Domain.EDGE.value},
                    },
                ),
                self._build_netconf_event(
                    "edge-comp-01",
                    {
                        "compute": {**self.compute.kpis(), "entityType": EntityType.COMPUTE_NODE.value},
                        "metadata": {"siteId": SITE_ID, "domain": Domain.EDGE.value},
                    },
                ),
            ]

            asyncio.create_task(self._emit(events))

            logger.info(
                "[SIM-EDGE tick=%.0f] sessions=%.0f latency=%.1fms saturation=%.2f",
                env.now, edge_sessions,
                self.edge_upf.forwarding_latency_ms,
                self.compute.saturation,
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
    engine = EdgeSimulationEngine()
    await engine.run()


if __name__ == "__main__":
    asyncio.run(main())
