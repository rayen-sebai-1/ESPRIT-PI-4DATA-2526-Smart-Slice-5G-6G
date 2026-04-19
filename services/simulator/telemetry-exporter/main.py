"""
telemetry-exporter/main.py
Prometheus Telemetry Exporter for neuroslice-sim.

Reads latest entity states from Redis hashes and
exposes them as Prometheus gauges on /metrics.
Also tracks event rate counters from stream stats.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Optional

import redis
from prometheus_client import (
    Counter, Gauge, start_http_server, generate_latest, CONTENT_TYPE_LATEST,
)
from fastapi import FastAPI
from fastapi.responses import Response
import uvicorn

sys.path.insert(0, "/shared")

from shared.config import get_config
from shared.redis_client import get_redis, list_entity_ids, get_entity_state

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

cfg = get_config()
app = FastAPI(title="neuroslice-sim telemetry-exporter")

# ─────────────────────────────────────────────────────────────────────────────
# Prometheus metrics
# ─────────────────────────────────────────────────────────────────────────────

emitted_events_total = Counter(
    "neuroslice_emitted_events_total", "Total events published to stream:norm.telemetry"
)
active_faults_gauge = Gauge("neuroslice_active_faults_total", "Currently active fault count")
congestion_score = Gauge(
    "neuroslice_congestion_score", "Entity congestion score", ["entity_id", "domain"]
)
health_score_g = Gauge(
    "neuroslice_health_score", "Entity health score", ["entity_id", "domain"]
)
misrouting_score_g = Gauge(
    "neuroslice_misrouting_score", "Entity misrouting score", ["entity_id", "domain"]
)
kpi_gauge = Gauge(
    "neuroslice_kpi", "Entity KPI value", ["entity_id", "domain", "kpi_name"]
)
severity_gauge = Gauge(
    "neuroslice_severity", "Entity severity level (0=OK, 4=CRITICAL)", ["entity_id", "domain"]
)

_redis: Optional[redis.Redis] = None


def get_r() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = get_redis()
    return _redis


async def scrape_loop() -> None:
    """Periodically update Prometheus metrics from Redis."""
    while True:
        try:
            r = get_r()

            # Active faults
            try:
                fault_count = len(r.hkeys("faults:active"))
                active_faults_gauge.set(fault_count)
            except Exception:
                pass

            # Stream stats — use XLEN for event counts
            try:
                norm_len = r.xlen(cfg.stream_norm_telemetry)
                for _ in range(max(0, norm_len - getattr(scrape_loop, "_prev_len", 0))):
                    emitted_events_total.inc()
                scrape_loop._prev_len = norm_len
            except Exception:
                pass

            # Entity-level metrics
            entity_ids = list_entity_ids(r)
            for eid in entity_ids:
                state = get_entity_state(r, eid)
                if not state:
                    continue
                domain = state.get("domain", "unknown")
                cs = float(state.get("congestionScore", 0.0))
                hs = float(state.get("healthScore", 1.0))
                ms = float(state.get("misroutingScore", 0.0))
                sev = float(state.get("severity", 0))

                congestion_score.labels(entity_id=eid, domain=domain).set(cs)
                health_score_g.labels(entity_id=eid, domain=domain).set(hs)
                misrouting_score_g.labels(entity_id=eid, domain=domain).set(ms)
                severity_gauge.labels(entity_id=eid, domain=domain).set(sev)

                # Per-KPI gauges
                kpis_raw = state.get("kpis", "{}")
                kpis = json.loads(kpis_raw) if isinstance(kpis_raw, str) else kpis_raw
                for kpi_name, kpi_val in (kpis or {}).items():
                    if isinstance(kpi_val, (int, float)):
                        kpi_gauge.labels(entity_id=eid, domain=domain, kpi_name=kpi_name).set(float(kpi_val))

        except Exception as exc:
            logger.warning("Scrape error: %s", exc)

        await asyncio.sleep(5)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "telemetry-exporter"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.on_event("startup")
async def startup() -> None:
    global _redis
    for attempt in range(20):
        try:
            _redis = get_redis()
            _redis.ping()
            logger.info("Exporter connected to Redis")
            break
        except Exception as exc:
            logger.warning("Waiting for Redis (%d/20): %s", attempt + 1, exc)
            await asyncio.sleep(3)
    asyncio.create_task(scrape_loop())


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9091, log_level="info")
