"""
api-service/main.py
FastAPI public API for neuroslice-sim.

Provides:
- Health / config
- Live KPI queries from Redis entity hashes
- Recent telemetry from stream:norm.telemetry
- Runtime AIOps output queries from aiops:* keys and events.* streams
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
from fastapi.responses import StreamingResponse
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
AIOPS_STREAMS = {
    "events.anomaly",
    "events.sla",
    "events.slice.classification",
}

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


def _decode_hash(raw: Dict[str, Any]) -> Dict[str, Any]:
    decoded = {}
    for key, value in raw.items():
        if isinstance(value, str):
            try:
                decoded[key] = json.loads(value)
            except Exception:
                decoded[key] = value
        else:
            decoded[key] = value
    return decoded


def _list_state_by_prefix(prefix: str, limit: int) -> List[Dict[str, Any]]:
    keys = get_r().keys(f"{prefix}:*")
    rows = []
    for key in keys:
        row = get_r().hgetall(key)
        if row:
            rows.append(_decode_hash(row))

    # Sort newest-first when timestamp exists.
    rows.sort(key=lambda item: str(item.get("timestamp", "")), reverse=True)
    return rows[:limit]


def _read_events_from_stream(stream_name: str, count: int) -> List[Dict[str, Any]]:
    messages = read_stream_latest(get_r(), stream_name, count=count)
    events: List[Dict[str, Any]] = []
    for _, fields in messages:
        raw = fields.get("event")
        if isinstance(raw, dict):
            events.append(raw)
            continue
        if isinstance(raw, str):
            try:
                events.append(json.loads(raw))
            except Exception:
                continue
    return events


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
# Live State Endpoints (React Dashboard)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/live/overview")
def get_live_overview() -> dict:
    """Return an overview of the network from Live State."""
    entity_ids = list_entity_ids(get_r())
    
    total_entities = len(entity_ids)
    unhealthy_count = 0
    congestion_count = 0
    sla_count = 0
    slice_mismatch_count = 0
    
    # Read active faults (if present)
    active_faults_count = 0
    try:
        faults_raw = get_r().get("faults:active")
        if faults_raw:
            faults = json.loads(faults_raw)
            active_faults_count = len(faults)
    except Exception:
        pass

    latest_entities = []
    
    for eid in entity_ids:
        state = get_entity_state(get_r(), eid)
        if not state:
            continue
            
        if isinstance(state.get("kpis"), str):
            try:
                state["kpis"] = json.loads(state["kpis"])
            except Exception:
                state["kpis"] = {}
                
        health = float(state.get("healthScore", 1.0))
        if health < 0.6:
            unhealthy_count += 1
            
        # Check AIOps risk embedded in entity (optional fallback if workers haven't fired, else check actual keys)
        # Using AIOps keys for accurate representation
        cg_state = get_r().hgetall(f"aiops:congestion:{eid}")
        if cg_state and str(_decode_hash(cg_state).get("prediction")) == "congestion_anomaly":
            congestion_count += 1
            
        sla_state = get_r().hgetall(f"aiops:sla:{eid}")
        if sla_state and str(_decode_hash(sla_state).get("prediction")) == "sla_at_risk":
            sla_count += 1
            
        sc_state = get_r().hgetall(f"aiops:slice_classification:{eid}")
        if sc_state:
            sc_decoded = _decode_hash(sc_state)
            if sc_decoded.get("details", {}).get("mismatch"):
                slice_mismatch_count += 1
                
        # To avoid making this massively blocking, just add the entity.
        latest_entities.append(state)

    latest_entities.sort(key=lambda x: str(x.get("timestamp", x.get("lastUpdated", ""))), reverse=True)
    latest_entities = latest_entities[:10]
    
    # Latest aiops events across streams
    recent_aiops = _read_events_from_stream("events.anomaly", count=5) + \
                   _read_events_from_stream("events.sla", count=5) + \
                   _read_events_from_stream("events.slice.classification", count=5)
    recent_aiops.sort(key=lambda x: str(x.get("timestamp", "")), reverse=True)

    return {
        "total_entities": total_entities,
        "active_faults_count": active_faults_count,
        "unhealthy_entities_count": unhealthy_count,
        "congestion_alerts_count": congestion_count,
        "sla_risk_count": sla_count,
        "slice_mismatch_count": slice_mismatch_count,
        "latest_entities": latest_entities,
        "latest_aiops_events": recent_aiops[:10]
    }


@app.get("/api/v1/live/entities")
def get_live_entities(limit: int = Query(100, le=500)) -> dict:
    entity_ids = list_entity_ids(get_r())
    results = []
    for eid in entity_ids:
        state = get_entity_state(get_r(), eid)
        if not state:
            continue
        if isinstance(state.get("kpis"), str):
            try:
                state["kpis"] = json.loads(state["kpis"])
            except Exception:
                state["kpis"] = {}
        results.append(state)
    
    results.sort(key=lambda x: str(x.get("timestamp", x.get("lastUpdated", ""))), reverse=True)
    results = results[:limit]
    return {"count": len(results), "items": results}


@app.get("/api/v1/live/entities/{entity_id}")
def get_live_entity(entity_id: str) -> dict:
    state = get_entity_state(get_r(), entity_id)
    if not state:
        raise HTTPException(404, f"Entity '{entity_id}' not found")
    if isinstance(state.get("kpis"), str):
        try:
            state["kpis"] = json.loads(state["kpis"])
        except Exception:
            state["kpis"] = {}
    return state


@app.get("/api/v1/live/entities/{entity_id}/aiops")
def get_live_entity_aiops(entity_id: str) -> dict:
    r = get_r()
    res = {}
    
    for prefix in ["aiops:congestion", "aiops:sla", "aiops:slice_classification"]:
        raw = r.hgetall(f"{prefix}:{entity_id}")
        prop_name = prefix.split(":")[-1]
        
        if raw:
            res[prop_name] = _decode_hash(raw)
        else:
            res[prop_name] = None
            
    return res


@app.get("/api/v1/live/faults")
def get_live_faults() -> dict:
    try:
        faults_raw = get_r().get("faults:active")
        if faults_raw:
            return {"faults": json.loads(faults_raw)}
        return {"faults": []}
    except Exception as exc:
        logger.warning(f"Failed to read faults from redis: {exc}")
        return {"faults": []}
        

@app.get("/api/v1/live/stream")
async def stream_live_events() -> StreamingResponse:
    """Server-Sent Events stream from norm.telemetry for the live dashboard."""
    consumer_group = "api-live-sse-group"
    consumer_name = "api-live-sse-01"

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
                logger.debug("SSE live stream error: %s", exc)
                yield f"data: {{\"error\": \"{exc}\"}}\n\n"
            await asyncio.sleep(0.1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ─────────────────────────────────────────────────────────────────────────────
# Runtime AIOps outputs
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/aiops/congestion/latest")
def get_latest_congestion_outputs(limit: int = Query(100, ge=1, le=1000)) -> dict:
    states = _list_state_by_prefix("aiops:congestion", limit)
    return {"count": len(states), "items": states}


@app.get("/api/v1/aiops/sla/latest")
def get_latest_sla_outputs(limit: int = Query(100, ge=1, le=1000)) -> dict:
    states = _list_state_by_prefix("aiops:sla", limit)
    return {"count": len(states), "items": states}


@app.get("/api/v1/aiops/slice-classification/latest")
def get_latest_slice_classification_outputs(limit: int = Query(100, ge=1, le=1000)) -> dict:
    states = _list_state_by_prefix("aiops:slice_classification", limit)
    return {"count": len(states), "items": states}


@app.get("/api/v1/aiops/events/recent")
def get_recent_aiops_events(
    stream: str = Query("events.anomaly"),
    count: int = Query(200, ge=1, le=2000),
) -> dict:
    if stream not in AIOPS_STREAMS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported stream '{stream}'. Allowed: {sorted(AIOPS_STREAMS)}",
        )
    events = _read_events_from_stream(stream, count)
    return {"stream": stream, "count": len(events), "events": events}


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
