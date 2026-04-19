"""
api-service/main.py
FastAPI public API for neuroslice-sim.

Provides:
- Health / config
- Live KPI queries from Redis entity hashes
- Recent telemetry from stream:norm.telemetry
- SSE streaming
- Fault/scenario control (proxy to fault-engine)
- ML dataset export endpoints
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
import redis
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

sys.path.insert(0, "/shared")

from shared.config import get_config
from shared.redis_client import (
    get_redis, read_stream_latest, list_entity_ids,
    get_entity_state, ensure_consumer_group, read_group, ack_message,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

cfg = get_config()
FAULT_ENGINE_URL = cfg.fault_engine_url

app = FastAPI(
    title="neuroslice-sim API",
    description="5G AIOps NWDAF-like telemetry simulator API",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_redis: Optional[redis.Redis] = None
_http: Optional[httpx.AsyncClient] = None


def get_r() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = get_redis()
    return _redis


# ─────────────────────────────────────────────────────────────────────────────
# Health / Config
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    try:
        get_r().ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return {
        "status": "ok" if redis_ok else "degraded",
        "service": "api-service",
        "redis": "up" if redis_ok else "down",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/config")
def config_info() -> dict:
    return {
        "site_id": cfg.site_id,
        "tick_interval_sec": cfg.tick_interval_sec,
        "sim_speed": cfg.sim_speed,
        "domains": ["core", "edge", "ran"],
        "slice_types": ["eMBB", "URLLC", "mMTC"],
        "entities": ["amf-01", "smf-01", "core-upf-01", "edge-upf-01", "mec-app-01",
                     "edge-comp-01", "gnb-01", "gnb-02"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Live KPI queries
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/kpis/latest")
def get_latest_kpis(
    domain: Optional[str] = Query(None, description="Filter by domain: core|edge|ran"),
    site_id: Optional[str] = Query(None, alias="siteId"),
    slice_id: Optional[str] = Query(None, alias="sliceId"),
    limit: int = Query(100, le=500),
) -> dict:
    """Return latest KPI snapshot for all entities (from Redis hashes)."""
    entity_ids = list_entity_ids(get_r())
    results = []
    for eid in entity_ids:
        state = get_entity_state(get_r(), eid)
        if not state:
            continue
        if domain and state.get("domain") != domain:
            continue
        if site_id and state.get("siteId") != site_id:
            continue
        # Unpack kpis from JSON string
        if isinstance(state.get("kpis"), str):
            try:
                state["kpis"] = json.loads(state["kpis"])
            except Exception:
                state["kpis"] = {}
        results.append(state)
        if len(results) >= limit:
            break
    return {"count": len(results), "entities": results}


@app.get("/api/v1/kpis/recent")
def get_recent_kpis(
    minutes: int = Query(15, ge=1, le=60),
    count: int = Query(500, le=2000),
) -> dict:
    """Return recent telemetry events from stream:norm.telemetry."""
    messages = read_stream_latest(get_r(), cfg.stream_norm_telemetry, count=count)
    events = []
    for msg_id, fields in messages:
        raw = fields.get("event")
        if raw:
            try:
                events.append(json.loads(raw) if isinstance(raw, str) else raw)
            except Exception:
                pass
    return {"count": len(events), "events": events}


@app.get("/api/v1/kpis/entity/{entity_id}")
def get_entity_kpis(entity_id: str) -> dict:
    """Return latest state for a specific entity."""
    state = get_entity_state(get_r(), entity_id)
    if not state:
        raise HTTPException(404, f"Entity '{entity_id}' not found")
    if isinstance(state.get("kpis"), str):
        state["kpis"] = json.loads(state["kpis"])
    return state


# ─────────────────────────────────────────────────────────────────────────────
# SSE streaming
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/stream/kpis")
async def stream_kpis() -> StreamingResponse:
    """Server-Sent Events stream from norm.telemetry."""
    consumer_group = "api-sse-group"
    consumer_name = "api-sse-01"

    try:
        ensure_consumer_group(get_r(), cfg.stream_norm_telemetry, consumer_group)
    except Exception:
        pass

    async def event_generator():
        yield "data: {\"status\": \"connected\"}\n\n"
        while True:
            try:
                messages = read_group(
                    get_r(), cfg.stream_norm_telemetry, consumer_group, consumer_name,
                    count=10, block_ms=1000,
                )
                for msg_id, fields in messages:
                    raw = fields.get("event")
                    if raw:
                        ack_message(get_r(), cfg.stream_norm_telemetry, consumer_group, msg_id)
                        payload = raw if isinstance(raw, str) else json.dumps(raw)
                        yield f"data: {payload}\n\n"
            except Exception as exc:
                logger.debug("SSE stream error: %s", exc)
                yield f"data: {{\"error\": \"{exc}\"}}\n\n"
            await asyncio.sleep(0.1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ─────────────────────────────────────────────────────────────────────────────
# Faults / Scenarios — proxy to fault-engine
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/faults/active")
async def get_active_faults() -> dict:
    try:
        resp = await _http.get(f"{FAULT_ENGINE_URL}/faults/active", timeout=5.0)
        return resp.json()
    except Exception as exc:
        raise HTTPException(503, f"fault-engine unavailable: {exc}")


class ScenarioStartRequest(BaseModel):
    scenario_id: str


class FaultInjectRequest(BaseModel):
    fault_type: str
    affected_entities: List[str] = []
    severity: int = 2
    duration_sec: float = 300.0
    kpi_impacts: Dict[str, float] = {}


@app.post("/api/v1/scenarios/start")
async def start_scenario(req: ScenarioStartRequest) -> dict:
    try:
        resp = await _http.post(f"{FAULT_ENGINE_URL}/scenarios/start", json=req.model_dump(), timeout=5.0)
        return resp.json()
    except Exception as exc:
        raise HTTPException(503, f"fault-engine unavailable: {exc}")


@app.post("/api/v1/scenarios/stop")
async def stop_scenario() -> dict:
    try:
        resp = await _http.post(f"{FAULT_ENGINE_URL}/scenarios/stop", timeout=5.0)
        return resp.json()
    except Exception as exc:
        raise HTTPException(503, f"fault-engine unavailable: {exc}")


@app.post("/api/v1/faults/inject")
async def inject_fault(req: FaultInjectRequest) -> dict:
    try:
        resp = await _http.post(f"{FAULT_ENGINE_URL}/faults/inject", json=req.model_dump(), timeout=5.0)
        return resp.json()
    except Exception as exc:
        raise HTTPException(503, f"fault-engine unavailable: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# ML dataset export endpoints
# ─────────────────────────────────────────────────────────────────────────────

def _read_all_norm_events(count: int = 2000) -> list:
    messages = read_stream_latest(get_r(), cfg.stream_norm_telemetry, count=count)
    events = []
    for _, fields in messages:
        raw = fields.get("event")
        if raw:
            try:
                events.append(json.loads(raw) if isinstance(raw, str) else raw)
            except Exception:
                pass
    return events


@app.get("/api/v1/export/sla")
def export_sla() -> dict:
    """
    SLA model feature view.
    Fields: packetLossPct, latencyMs, sliceType encoded columns, sla_met
    """
    events = _read_all_norm_events()
    rows = []
    for ev in events:
        kpis = ev.get("kpis", {})
        slice_type = ev.get("sliceType", "")
        rows.append({
            "timestamp": ev.get("timestamp"),
            "entityId": ev.get("entityId"),
            "sliceType": slice_type,
            "packetLossPct": kpis.get("packetLossPct", 0.0),
            "latencyMs": kpis.get("latencyMs", 0.0),
            "isSmartCity": 1 if slice_type == "mMTC" else 0,
            "isIoT": 1 if slice_type == "mMTC" else 0,
            "isPublicSafety": 1 if slice_type == "URLLC" else 0,
            "scenarioId": ev.get("scenarioId", "normal_day"),
            "congestionScore": ev.get("derived", {}).get("congestionScore", 0.0),
            "sla_met": 1 if ev.get("derived", {}).get("healthScore", 1.0) > 0.6 else 0,
        })
    return {"count": len(rows), "schema": "sla_feature_view", "data": rows}


@app.get("/api/v1/export/slice-classifier")
def export_slice_classifier() -> dict:
    """
    Slice classifier feature view.
    Fields: slice category, packetLoss, latency, UE type flags, GBR, sliceType label
    """
    events = _read_all_norm_events()
    rows = []
    for ev in events:
        kpis = ev.get("kpis", {})
        slice_type = ev.get("sliceType", "")
        gbr = {"eMBB": 1, "URLLC": 1, "mMTC": 0}.get(slice_type, 0)
        rows.append({
            "timestamp": ev.get("timestamp"),
            "entityId": ev.get("entityId"),
            "lte5gCategory": 2,  # 5G NR
            "packetLossPct": kpis.get("packetLossPct", 0.0),
            "latencyMs": kpis.get("latencyMs", 0.0),
            "isSmartphone": 1 if slice_type == "eMBB" else 0,
            "isIoT": 1 if slice_type == "mMTC" else 0,
            "gbr": gbr,
            "sliceType": slice_type,
            "sliceTypeEncoded": {"eMBB": 0, "URLLC": 1, "mMTC": 2}.get(slice_type, -1),
        })
    return {"count": len(rows), "schema": "slice_classifier_feature_view", "data": rows}


@app.get("/api/v1/export/congestion-sequences")
def export_congestion_sequences() -> dict:
    """
    LSTM feature view — ordered sequences of latent state per slice.
    Fields: cpuUtil, memUtil, bwUtil, activeUsers, queueLen, hour, sliceTypeEncoded, congestionFlag
    """
    # Read entity states for LSTM features
    entity_ids = list_entity_ids(get_r())
    rows = []
    for eid in entity_ids:
        state = get_entity_state(get_r(), eid)
        if not state:
            continue
        kpis_raw = state.get("kpis", "{}")
        kpis = json.loads(kpis_raw) if isinstance(kpis_raw, str) else kpis_raw
        domain = state.get("domain", "")
        congestion = float(state.get("congestionScore", 0.0))

        # Only emit for compute-intensive entities
        if domain not in ("core", "edge", "ran"):
            continue

        hour = datetime.fromisoformat(state.get("lastUpdated", datetime.now().isoformat())).hour
        slice_type_str = kpis.get("sliceType", "")
        rows.append({
            "entityId": eid,
            "domain": domain,
            "timestamp": state.get("lastUpdated"),
            "cpuUtilPct": kpis.get("cpuUtilPct", 0.0),
            "memUtilPct": kpis.get("memUtilPct", 0.0),
            "bwUtilPct": kpis.get("rbUtilizationPct", kpis.get("queueDepthPct", 0.0)),
            "activeUsers": kpis.get("ueCount", kpis.get("activeUeCount", 0)),
            "queueLen": kpis.get("registrationQueueLen", kpis.get("pduSetupQueueLen", 0.0)),
            "hour": hour,
            "sliceTypeEncoded": -1,  # entity-level, not slice-level
            "congestionScore": congestion,
            "congestionFlag": 1 if congestion > 0.7 else 0,
        })
    return {"count": len(rows), "schema": "congestion_lstm_feature_view", "data": rows}


# ─────────────────────────────────────────────────────────────────────────────
# Lifecycle
# ─────────────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup() -> None:
    global _redis, _http
    _http = httpx.AsyncClient()
    for attempt in range(20):
        try:
            _redis = get_redis()
            _redis.ping()
            logger.info("API service connected to Redis")
            return
        except Exception as exc:
            logger.warning("Waiting for Redis (%d/20): %s", attempt + 1, exc)
            await asyncio.sleep(3)


@app.on_event("shutdown")
async def shutdown() -> None:
    if _http:
        await _http.aclose()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
