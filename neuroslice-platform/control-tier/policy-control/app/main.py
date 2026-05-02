"""FastAPI entrypoint for deterministic Policy Control."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import redis
from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
import uvicorn

from .action_store import ActionStore
from .config import get_config
from .consumer import PolicyConsumer
from .policy_engine import PolicyEngine
from .redis_client import get_redis
from .simulation_actuator import SimulationActuator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("policy-control")

cfg = get_config()
app = FastAPI(
    title="NeuroSlice Policy Control",
    version="1.0.0",
    description="Deterministic human-in-the-loop Control Tier policy service. No LLM calls.",
)

_redis: redis.Redis | None = None
_store: ActionStore | None = None
_consumer: PolicyConsumer | None = None
_consumer_task: asyncio.Task | None = None


def get_r() -> redis.Redis:
    if _redis is None:
        raise HTTPException(status_code=503, detail="Redis is not connected.")
    return _redis


def get_store() -> ActionStore:
    if _store is None:
        raise HTTPException(status_code=503, detail="Action store is not ready.")
    return _store


@app.get("/health")
def health() -> dict[str, str]:
    redis_status = "down"
    status = "degraded"
    try:
        get_r().ping()
        redis_status = "up"
        status = "ok"
    except Exception:
        pass

    return {
        "status": status,
        "service": cfg.service_name,
        "redis": redis_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/actions")
def list_actions() -> dict:
    items = get_store().list_actions()
    return {"count": len(items), "items": items}


@app.get("/actions/{action_id}")
def get_action(action_id: str) -> dict:
    action = get_store().get_action(action_id)
    if action is None:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found.")
    return action


@app.post("/actions/{action_id}/approve")
def approve_action(action_id: str) -> dict:
    try:
        action = get_store().approve(action_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if action is None:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found.")
    return action


@app.post("/actions/{action_id}/reject")
def reject_action(action_id: str) -> dict:
    try:
        action = get_store().reject(action_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if action is None:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found.")
    return action


@app.post("/actions/{action_id}/execute")
def execute_action(action_id: str) -> dict:
    try:
        action = get_store().execute(action_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if action is None:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found.")
    return action


@app.get("/actuations")
def list_actuations() -> dict:
    items = get_store().list_actuations()
    return {"count": len(items), "items": items}


@app.get("/actuations/{action_id}")
def get_actuation(action_id: str) -> dict:
    actuation = get_store().get_actuation(action_id)
    if actuation is None:
        raise HTTPException(status_code=404, detail=f"Actuation '{action_id}' not found.")
    return actuation


@app.on_event("startup")
async def startup() -> None:
    global _redis, _store, _consumer, _consumer_task
    for attempt in range(30):
        try:
            _redis = get_redis(cfg)
            _redis.ping()
            _store = ActionStore(cfg, _redis, PolicyEngine(), SimulationActuator(cfg, _redis))
            _consumer = PolicyConsumer(cfg, _redis, _store)
            _consumer_task = asyncio.create_task(_consumer.run_forever())
            logger.info("Policy Control connected to Redis")
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("Waiting for Redis (%d/30): %s", attempt + 1, exc)
            await asyncio.sleep(2.0)
    raise RuntimeError("Could not connect to Redis")


@app.on_event("shutdown")
async def shutdown() -> None:
    if _consumer is not None:
        _consumer.stop()
    if _consumer_task is not None:
        _consumer_task.cancel()
        await asyncio.gather(_consumer_task, return_exceptions=True)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=cfg.service_port, log_level="info")
