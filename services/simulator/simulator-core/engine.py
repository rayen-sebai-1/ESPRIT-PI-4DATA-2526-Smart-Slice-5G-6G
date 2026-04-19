"""
simulator-core/engine.py
SimPy-based discrete-event tick engine for the Core domain.

Reads fault state from Redis, updates entity states, and emits
telemetry to the VES adapter on every tick.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
import redis
import simpy


from shared.config import get_config
from shared.models import Domain, EntityType, Protocol, RawVesEvent
from shared.redis_client import get_redis

from entities.amf import AMFState
from entities.smf import SMFState
from entities.upf import UPFState

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)

cfg = get_config()

SITE_ID = cfg.site_id
VES_ADAPTER_URL = cfg.ves_adapter_url


class CoreSimulationEngine:
    """Runs the Core domain simulation using SimPy."""

    def __init__(self) -> None:
        self.env = simpy.Environment()
        self.amf = AMFState()
        self.smf = SMFState()
        self.upf = UPFState()
        self.redis: Optional[redis.Redis] = None
        self.current_scenario: str = "normal_day"
        self.traffic_modifier: float = 1.0
        self.http_client: Optional[httpx.AsyncClient] = None
        self._active_faults: dict = {}

    def _sim_time_to_hour(self) -> float:
        """Map simulated time (seconds) to hour of day (0–24)."""
        sim_seconds = self.env.now * cfg.sim_speed
        return (sim_seconds / 3600) % 24

    def _load_fault_state(self) -> None:
        """Pull current fault impacts from Redis hash `faults:active`."""
        if self.redis is None:
            return
        try:
            raw = self.redis.hgetall("faults:active")
            if not raw:
                # Reset fault state if no active faults
                self.amf.fault_degradation = 0.0
                self.amf.fault_cpu_spike = 0.0
                self.smf.fault_degradation = 0.0
                self.upf.fault_overload = 0.0
                self.upf.fault_packet_loss = 0.0
                self.upf.misrouting_extra_load = 0.0
                return

            self._active_faults = {k: json.loads(v) for k, v in raw.items()}
            # Apply impacts from each active fault
            amf_deg = 0.0
            upf_overload = 0.0
            upf_pl = 0.0
            misrouting = 0.0
            scenario = "normal_day"

            for fault_id, fault in self._active_faults.items():
                impacts = fault.get("kpi_impacts", {})
                ft = fault.get("fault_type", "")
                if ft == "amf_degradation":
                    amf_deg = max(amf_deg, impacts.get("degradation", 0.3))
                elif ft == "upf_overload":
                    upf_overload = max(upf_overload, impacts.get("overload", 0.4))
                    upf_pl = max(upf_pl, impacts.get("packet_loss", 0.02))
                elif ft == "slice_misrouting":
                    misrouting = max(misrouting, impacts.get("extra_gbps", 2.0))
                elif ft == "packet_loss_spike":
                    upf_pl = max(upf_pl, impacts.get("packet_loss", 0.05))
                scenario = fault.get("scenario_id", scenario)

            self.amf.fault_degradation = amf_deg
            self.amf.fault_cpu_spike = amf_deg * 0.2
            self.smf.fault_degradation = amf_deg * 0.5
            self.upf.fault_overload = upf_overload
            self.upf.fault_packet_loss = upf_pl
            self.upf.misrouting_extra_load = misrouting
            self.current_scenario = scenario

        except Exception as exc:
            logger.warning("Could not load fault state: %s", exc)

    def _build_event(self, entity_id: str, entity_type: str, kpis: dict, internal: dict = {}) -> dict:
        ts = datetime.now(timezone.utc).isoformat()
        return RawVesEvent(
            source="simulator-core",
            domain=Domain.CORE.value,
            entity_id=entity_id,
            entity_type=entity_type,
            site_id=SITE_ID,
            node_id="core-node-01",
            timestamp=ts,
            kpis=kpis,
            internal=internal,
            scenario_id=self.current_scenario,
        ).model_dump()

    async def _emit(self, events: list[dict]) -> None:
        """Send telemetry batch to VES adapter."""
        if self.http_client is None:
            return
        for event in events:
            try:
                resp = await self.http_client.post(
                    f"{VES_ADAPTER_URL}/events",
                    json=event,
                    timeout=3.0,
                )
                if resp.status_code not in (200, 202):
                    logger.warning("VES adapter returned %d", resp.status_code)
            except Exception as exc:
                logger.debug("VES emit error: %s", exc)

    def tick(self, env: simpy.Environment):
        """SimPy generator — one tick per configured interval."""
        while True:
            hour = self._sim_time_to_hour()
            self._load_fault_state()

            # ── Update entity states (causally chained) ──────────────────
            self.amf.update(hour, self.traffic_modifier)
            self.smf.update(self.amf.active_ues, self.traffic_modifier)
            ran_congestion = 0.0  # will be filled by RAN simulator via Redis
            try:
                if self.redis:
                    val = self.redis.get("ran:congestion_score")
                    if val:
                        ran_congestion = float(val)
            except Exception:
                pass
            self.upf.update(self.smf.active_sessions, ran_congestion)

            # ── Build events ─────────────────────────────────────────────
            events = [
                self._build_event("amf-01", EntityType.AMF.value, self.amf.kpis()),
                self._build_event("smf-01", EntityType.SMF.value, self.smf.kpis()),
                self._build_event(
                    "core-upf-01",
                    EntityType.UPF.value,
                    self.upf.kpis(),
                    {"misroutingExtraGbps": self.upf.misrouting_extra_load},
                ),
            ]

            # Emit async in background (don't block SimPy env)
            asyncio.create_task(self._emit(events))

            logger.info(
                "[SIM-CORE tick=%.0f h=%.1f] UEs=%d sessions=%d dl=%.2f Gbps",
                env.now,
                hour,
                self.amf.active_ues,
                self.smf.active_sessions,
                self.upf.dl_throughput_gbps,
            )

            yield env.timeout(1)  # 1 SimPy time unit = tick_interval_sec real seconds

    async def run(self) -> None:
        """Async main loop — bridges asyncio and SimPy."""
        # Connect to Redis
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

        # Run SimPy in a tight loop, sleeping real time between ticks
        while True:
            self.env.step()
            await asyncio.sleep(cfg.tick_interval_sec)


async def main() -> None:
    engine = CoreSimulationEngine()
    await engine.run()


if __name__ == "__main__":
    asyncio.run(main())
