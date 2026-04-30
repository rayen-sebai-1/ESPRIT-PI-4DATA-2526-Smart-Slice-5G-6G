"""Drift Monitor — watches AIOps output streams for statistical drift signals,
then triggers the MLOps pipeline automatically via mlops-runner.

Security:
- mlops-runner calls use a shared bearer token (MLOPS_RUNNER_TOKEN)
- cooldown window prevents trigger storms
- drift decisions are stored in Redis for dashboard visibility
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import UTC, datetime
from typing import Any

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("drift-monitor")

app = FastAPI(title="NeuroSlice Drift Monitor", version="1.0.0")

# ── configuration ─────────────────────────────────────────────────────────────

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

MLOPS_RUNNER_URL = os.getenv("MLOPS_RUNNER_URL", "http://mlops-runner:8020")
MLOPS_RUNNER_TOKEN = os.getenv("MLOPS_RUNNER_TOKEN", "secret_runner_token_123")
MLOPS_PIPELINE_ENABLED = os.getenv("MLOPS_PIPELINE_ENABLED", "false").lower() in {"1", "true", "yes"}

# Streams that carry AIOps anomaly events
ANOMALY_STREAM = os.getenv("DRIFT_ANOMALY_STREAM", "events.anomaly")
DRIFT_STREAM = os.getenv("DRIFT_OUTPUT_STREAM", "events.drift")

# How many anomaly events in the look-back window trigger drift
DRIFT_ANOMALY_THRESHOLD = int(os.getenv("DRIFT_ANOMALY_THRESHOLD", "5"))
DRIFT_WINDOW_SECONDS = int(os.getenv("DRIFT_WINDOW_SECONDS", "120"))

# Minimum seconds between two automatic pipeline triggers
DRIFT_COOLDOWN_SECONDS = int(os.getenv("DRIFT_COOLDOWN_SECONDS", "600"))

POLL_INTERVAL_SECONDS = float(os.getenv("DRIFT_POLL_INTERVAL_SECONDS", "30"))

# Redis key that stores the last trigger timestamp
_LAST_TRIGGER_KEY = "drift:last_trigger_ts"
_DRIFT_STATUS_KEY = "drift:status"
_DRIFT_EVENTS_KEY = "drift:events"

# ── state ─────────────────────────────────────────────────────────────────────

_redis: aioredis.Redis | None = None
_monitor_task: asyncio.Task | None = None
_last_stream_id: str = "0-0"


class DriftStatus(BaseModel):
    drift_detected: bool
    p_value: float | None
    anomaly_count: int
    window_seconds: int
    threshold: int
    last_detection_time: str | None
    last_trigger_time: str | None
    pipeline_triggered: bool
    cooldown_active: bool
    pipeline_enabled: bool


# ── helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _now_ts() -> float:
    return time.time()


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    return _redis


async def _count_recent_anomalies(r: aioredis.Redis) -> int:
    """Count anomaly events in the last DRIFT_WINDOW_SECONDS from Redis stream."""
    cutoff_ms = int((_now_ts() - DRIFT_WINDOW_SECONDS) * 1000)
    cutoff_id = f"{cutoff_ms}-0"
    try:
        entries = await r.xrange(ANOMALY_STREAM, min=cutoff_id)
        return len(entries)
    except Exception as exc:
        logger.warning("Could not read anomaly stream: %s", exc)
        return 0


async def _is_in_cooldown(r: aioredis.Redis) -> bool:
    last_ts_str = await r.get(_LAST_TRIGGER_KEY)
    if last_ts_str is None:
        return False
    try:
        elapsed = _now_ts() - float(last_ts_str)
        return elapsed < DRIFT_COOLDOWN_SECONDS
    except ValueError:
        return False


async def _record_trigger(r: aioredis.Redis) -> None:
    await r.set(_LAST_TRIGGER_KEY, str(_now_ts()))


async def _publish_drift_event(r: aioredis.Redis, anomaly_count: int) -> None:
    payload = {
        "event_type": "drift_detected",
        "anomaly_count": str(anomaly_count),
        "window_seconds": str(DRIFT_WINDOW_SECONDS),
        "threshold": str(DRIFT_ANOMALY_THRESHOLD),
        "timestamp": _now_iso(),
    }
    try:
        await r.xadd(DRIFT_STREAM, payload, maxlen=1000)
    except Exception as exc:
        logger.warning("Could not publish drift event: %s", exc)


async def _save_drift_status(r: aioredis.Redis, status: dict[str, Any]) -> None:
    try:
        await r.set(_DRIFT_STATUS_KEY, json.dumps(status))
        await r.lpush(_DRIFT_EVENTS_KEY, json.dumps(status))
        await r.ltrim(_DRIFT_EVENTS_KEY, 0, 99)
    except Exception as exc:
        logger.warning("Could not save drift status: %s", exc)


async def _trigger_mlops_pipeline(anomaly_count: int) -> bool:
    """Call mlops-runner to trigger the full pipeline. Returns True on success."""
    if not MLOPS_PIPELINE_ENABLED:
        logger.info("MLOPS_PIPELINE_ENABLED=false — skipping auto trigger")
        return False
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{MLOPS_RUNNER_URL}/run-action",
                json={
                    "action": "full_pipeline",
                    "trigger_source": "drift",
                    "parameters": {"DRIFT_ANOMALY_COUNT": str(anomaly_count)},
                },
                headers={"Authorization": f"Bearer {MLOPS_RUNNER_TOKEN}"},
            )
            if resp.status_code == 200:
                logger.info("Pipeline triggered via drift — response: %s", resp.json().get("accepted"))
                return True
            logger.warning("mlops-runner returned %s: %s", resp.status_code, resp.text[:200])
            return False
    except Exception as exc:
        logger.error("Failed to call mlops-runner: %s", exc)
        return False


# ── monitoring loop ───────────────────────────────────────────────────────────

async def _monitor_loop() -> None:
    logger.info("Drift monitor started — poll=%ss threshold=%d window=%ds cooldown=%ds",
                POLL_INTERVAL_SECONDS, DRIFT_ANOMALY_THRESHOLD, DRIFT_WINDOW_SECONDS, DRIFT_COOLDOWN_SECONDS)

    r = await _get_redis()
    while True:
        try:
            anomaly_count = await _count_recent_anomalies(r)
            drift_detected = anomaly_count >= DRIFT_ANOMALY_THRESHOLD
            cooldown = await _is_in_cooldown(r)
            pipeline_triggered = False
            last_trigger_str = await r.get(_LAST_TRIGGER_KEY)
            last_trigger_time = (
                datetime.fromtimestamp(float(last_trigger_str), UTC).isoformat()
                if last_trigger_str else None
            )

            if drift_detected and not cooldown:
                logger.warning("DRIFT DETECTED — %d anomalies in %ds window. Triggering pipeline.",
                               anomaly_count, DRIFT_WINDOW_SECONDS)
                await _publish_drift_event(r, anomaly_count)
                pipeline_triggered = await _trigger_mlops_pipeline(anomaly_count)
                if pipeline_triggered:
                    await _record_trigger(r)
                    last_trigger_time = _now_iso()
            elif drift_detected and cooldown:
                logger.info("Drift detected but cooldown active — skipping trigger")

            status = {
                "drift_detected": drift_detected,
                "p_value": None,
                "anomaly_count": anomaly_count,
                "window_seconds": DRIFT_WINDOW_SECONDS,
                "threshold": DRIFT_ANOMALY_THRESHOLD,
                "last_detection_time": _now_iso() if drift_detected else None,
                "last_trigger_time": last_trigger_time,
                "pipeline_triggered": pipeline_triggered,
                "cooldown_active": cooldown,
                "pipeline_enabled": MLOPS_PIPELINE_ENABLED,
            }
            await _save_drift_status(r, status)

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Monitor loop error: %s", exc)

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


# ── API endpoints ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    r = await _get_redis()
    redis_ok = False
    try:
        await r.ping()
        redis_ok = True
    except Exception:
        pass
    return {
        "status": "ok" if redis_ok else "degraded",
        "service": "drift-monitor",
        "redis": "up" if redis_ok else "down",
        "pipeline_enabled": MLOPS_PIPELINE_ENABLED,
        "timestamp": _now_iso(),
    }


@app.get("/drift/status", response_model=DriftStatus)
async def drift_status() -> DriftStatus:
    r = await _get_redis()
    raw = await r.get(_DRIFT_STATUS_KEY)
    if raw:
        data = json.loads(raw)
        return DriftStatus(**data)

    anomaly_count = await _count_recent_anomalies(r)
    cooldown = await _is_in_cooldown(r)
    return DriftStatus(
        drift_detected=False,
        p_value=None,
        anomaly_count=anomaly_count,
        window_seconds=DRIFT_WINDOW_SECONDS,
        threshold=DRIFT_ANOMALY_THRESHOLD,
        last_detection_time=None,
        last_trigger_time=None,
        pipeline_triggered=False,
        cooldown_active=cooldown,
        pipeline_enabled=MLOPS_PIPELINE_ENABLED,
    )


@app.get("/drift/events")
async def drift_events(limit: int = 20) -> dict:
    r = await _get_redis()
    raw_list = await r.lrange(_DRIFT_EVENTS_KEY, 0, min(limit, 100) - 1)
    events = []
    for raw in raw_list:
        try:
            events.append(json.loads(raw))
        except Exception:
            pass
    return {"count": len(events), "items": events}


@app.post("/drift/trigger")
async def manual_trigger() -> dict:
    """Manually trigger a drift check and pipeline (for testing)."""
    r = await _get_redis()
    anomaly_count = await _count_recent_anomalies(r)
    cooldown = await _is_in_cooldown(r)
    if cooldown:
        return {"triggered": False, "reason": "cooldown_active", "anomaly_count": anomaly_count}
    await _publish_drift_event(r, anomaly_count)
    ok = await _trigger_mlops_pipeline(anomaly_count)
    if ok:
        await _record_trigger(r)
    return {"triggered": ok, "reason": "manual", "anomaly_count": anomaly_count}


@app.on_event("startup")
async def startup() -> None:
    global _monitor_task
    r = await _get_redis()
    for attempt in range(30):
        try:
            await r.ping()
            logger.info("Connected to Redis")
            break
        except Exception as exc:
            logger.warning("Waiting for Redis (%d/30): %s", attempt + 1, exc)
            await asyncio.sleep(2.0)
    _monitor_task = asyncio.create_task(_monitor_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    global _monitor_task
    if _monitor_task:
        _monitor_task.cancel()
        await asyncio.gather(_monitor_task, return_exceptions=True)
