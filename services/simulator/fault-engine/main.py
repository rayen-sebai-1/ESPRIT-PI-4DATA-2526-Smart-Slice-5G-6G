"""
fault-engine/main.py
Fault Engine Service — loads scenarios, schedules fault injections,
and maintains the `faults:active` Redis hash consumed by all simulators.
Exposes REST endpoints for manual fault injection and scenario control.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

sys.path.insert(0, "/shared")

from shared.config import get_config
from shared.models import FaultEvent, FaultType, ScenarioDefinition, Severity
from shared.redis_client import get_redis, publish_to_stream

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

cfg = get_config()
SCENARIOS_DIR = Path(os.getenv("SCENARIOS_DIR", "/scenarios"))

app = FastAPI(title="neuroslice-sim fault-engine", version="1.0.0")

# ─────────────────────────────────────────────────────────────────────────────
# State
# ─────────────────────────────────────────────────────────────────────────────
_redis: Optional[redis.Redis] = None
_active_faults: Dict[str, dict] = {}
_active_scenario: Optional[str] = None
_scenario_task: Optional[asyncio.Task] = None


def get_r() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = get_redis()
    return _redis


# ─────────────────────────────────────────────────────────────────────────────
# Fault management
# ─────────────────────────────────────────────────────────────────────────────

def _activate_fault(fault_dict: dict) -> str:
    """Write fault to Redis hash and local state."""
    fault_id = fault_dict.get("fault_id") or str(uuid.uuid4())
    fault_dict["fault_id"] = fault_id
    fault_dict["activated_at"] = datetime.now(timezone.utc).isoformat()
    _active_faults[fault_id] = fault_dict
    try:
        get_r().hset("faults:active", fault_id, json.dumps(fault_dict))
        publish_to_stream(get_r(), cfg.stream_fault_events, {"event": "fault_activated", "fault_id": fault_id, "data": json.dumps(fault_dict)})
    except Exception as exc:
        logger.error("Redis fault write error: %s", exc)
    logger.info("FAULT ACTIVATED: %s type=%s", fault_id, fault_dict.get("fault_type"))
    return fault_id


def _deactivate_fault(fault_id: str) -> None:
    """Remove fault from Redis and local state."""
    _active_faults.pop(fault_id, None)
    try:
        get_r().hdel("faults:active", fault_id)
        publish_to_stream(get_r(), cfg.stream_fault_events, {"event": "fault_cleared", "fault_id": fault_id})
    except Exception as exc:
        logger.error("Redis fault clear error: %s", exc)
    logger.info("FAULT CLEARED: %s", fault_id)


async def _schedule_fault_expiry(fault_id: str, duration_sec: float) -> None:
    await asyncio.sleep(duration_sec)
    if fault_id in _active_faults:
        _deactivate_fault(fault_id)


# ─────────────────────────────────────────────────────────────────────────────
# Scenario runner
# ─────────────────────────────────────────────────────────────────────────────

def _load_scenario(scenario_id: str) -> Optional[dict]:
    path = SCENARIOS_DIR / f"{scenario_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


async def _run_scenario(scenario: dict) -> None:
    global _active_scenario
    scenario_id = scenario["scenario_id"]
    _active_scenario = scenario_id
    logger.info("SCENARIO STARTED: %s", scenario_id)

    # Inject all faults from the scenario definition
    fault_ids = []
    for fault_def in scenario.get("faults", []):
        fault_def = {**fault_def}
        fault_def["scenario_id"] = scenario_id
        fault_def["traffic_modifier"] = scenario.get("traffic_modifier", 1.0)
        fid = _activate_fault(fault_def)
        fault_ids.append((fid, fault_def.get("duration_sec", 300)))

    # Schedule individual fault expiries
    tasks = [asyncio.create_task(_schedule_fault_expiry(fid, dur)) for fid, dur in fault_ids]

    # Wait for scenario total duration
    await asyncio.sleep(scenario.get("duration_sec", 3600))

    # Cancel pending expiry tasks and clear remaining faults
    for t in tasks:
        t.cancel()
    for fid, _ in fault_ids:
        if fid in _active_faults:
            _deactivate_fault(fid)

    _active_scenario = None
    logger.info("SCENARIO ENDED: %s", scenario_id)


# ─────────────────────────────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────────────────────────────

class FaultInjectRequest(BaseModel):
    fault_type: str
    affected_entities: List[str] = []
    severity: int = 2
    duration_sec: float = 300.0
    kpi_impacts: Dict[str, float] = {}
    scenario_id: str = "manual"


class ScenarioRequest(BaseModel):
    scenario_id: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "fault-engine"}


@app.get("/faults/active")
def get_active_faults() -> dict:
    return {"active_faults": list(_active_faults.values()), "count": len(_active_faults)}


@app.get("/scenarios")
def list_scenarios() -> dict:
    scenarios = [p.stem for p in SCENARIOS_DIR.glob("*.json")]
    return {"scenarios": scenarios, "active": _active_scenario}


@app.post("/scenarios/start")
async def start_scenario(req: ScenarioRequest) -> dict:
    global _scenario_task
    scenario = _load_scenario(req.scenario_id)
    if not scenario:
        raise HTTPException(404, f"Scenario '{req.scenario_id}' not found")

    if _scenario_task and not _scenario_task.done():
        _scenario_task.cancel()

    _scenario_task = asyncio.create_task(_run_scenario(scenario))
    return {"status": "started", "scenario_id": req.scenario_id}


@app.post("/scenarios/stop")
async def stop_scenario() -> dict:
    global _scenario_task, _active_scenario
    if _scenario_task and not _scenario_task.done():
        _scenario_task.cancel()
    # Clear all active faults
    for fault_id in list(_active_faults.keys()):
        _deactivate_fault(fault_id)
    _active_scenario = None
    return {"status": "stopped"}


@app.post("/faults/inject")
async def inject_fault(req: FaultInjectRequest) -> dict:
    fault_dict = req.model_dump()
    fault_id = _activate_fault(fault_dict)
    asyncio.create_task(_schedule_fault_expiry(fault_id, req.duration_sec))
    return {"status": "injected", "fault_id": fault_id}


@app.on_event("startup")
async def startup() -> None:
    global _redis
    for attempt in range(20):
        try:
            _redis = get_redis()
            _redis.ping()
            logger.info("Connected to Redis")
            # Clear any stale faults from previous runs
            _redis.delete("faults:active")
            break
        except Exception as exc:
            logger.warning("Waiting for Redis (%d/20): %s", attempt + 1, exc)
            await asyncio.sleep(3)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7004, log_level="info")
