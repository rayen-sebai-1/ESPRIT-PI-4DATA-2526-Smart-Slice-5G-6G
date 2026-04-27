"""FastAPI entrypoint for deterministic Alert Management."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import redis
from fastapi import FastAPI, HTTPException
import uvicorn

from .alert_store import AlertStore
from .config import get_config
from .consumer import AlertConsumer
from .redis_client import get_redis

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("alert-management")

cfg = get_config()
app = FastAPI(
    title="NeuroSlice Alert Management",
    version="1.0.0",
    description="Deterministic Control Tier alert lifecycle service. No LLM calls.",
)

_redis: redis.Redis | None = None
_store: AlertStore | None = None
_consumer: AlertConsumer | None = None
_consumer_task: asyncio.Task | None = None


def get_r() -> redis.Redis:
    if _redis is None:
        raise HTTPException(status_code=503, detail="Redis is not connected.")
    return _redis


def get_store() -> AlertStore:
    if _store is None:
        raise HTTPException(status_code=503, detail="Alert store is not ready.")
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


@app.get("/alerts")
def list_alerts() -> dict:
    items = get_store().list_alerts()
    return {"count": len(items), "items": items}


@app.get("/alerts/{alert_id}")
def get_alert(alert_id: str) -> dict:
    alert = get_store().get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    return alert


@app.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str) -> dict:
    try:
        alert = get_store().acknowledge(alert_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    return alert


@app.post("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: str) -> dict:
    try:
        alert = get_store().resolve(alert_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    return alert


@app.on_event("startup")
async def startup() -> None:
    global _redis, _store, _consumer, _consumer_task
    for attempt in range(30):
        try:
            _redis = get_redis(cfg)
            _redis.ping()
            _store = AlertStore(cfg, _redis)
            _consumer = AlertConsumer(cfg, _redis, _store)
            _consumer_task = asyncio.create_task(_consumer.run_forever())
            logger.info("Alert Management connected to Redis")
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
