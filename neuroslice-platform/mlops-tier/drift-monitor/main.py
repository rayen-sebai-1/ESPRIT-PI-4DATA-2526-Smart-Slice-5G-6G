"""Drift monitor that observes anomaly streams and creates retraining requests.

Human-in-the-loop behavior:
- drift detection never executes training directly
- drift detection writes pending approval requests into Redis
- execution is delegated to dashboard approval APIs
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as aioredis
from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("drift-monitor")

app = FastAPI(title="NeuroSlice Drift Monitor", version="2.0.0")

# configuration ----------------------------------------------------------------

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

AUTO_RETRAIN_ENABLED = os.getenv("AUTO_RETRAIN_ENABLED", "false").strip().lower() in {"1", "true", "yes"}

# Per-model stream -> pipeline mapping.
_MODEL_CONFIG: dict[str, dict[str, str]] = {
    "congestion_5g": {
        "stream": os.getenv("DRIFT_CONGESTION_STREAM", "events.anomaly"),
        "pipeline_action": "pipeline_congestion_5g",
    },
    "sla_5g": {
        "stream": os.getenv("DRIFT_SLA_STREAM", "events.sla"),
        "pipeline_action": "pipeline_sla_5g",
    },
    "slice_type_5g": {
        "stream": os.getenv("DRIFT_SLICE_STREAM", "events.slice.classification"),
        "pipeline_action": "pipeline_slice_type_5g",
    },
}

_ANOMALY_PREDICTIONS: dict[str, set[str]] = {
    "congestion_5g": {"congestion_anomaly"},
    "sla_5g": {"sla_at_risk"},
}

_MODEL_PUBLIC_NAME: dict[str, str] = {
    "congestion_5g": "congestion-5g",
    "sla_5g": "sla-5g",
    "slice_type_5g": "slice-type-5g",
}

DRIFT_ANOMALY_THRESHOLD = int(os.getenv("DRIFT_ANOMALY_THRESHOLD", "15"))
DRIFT_WINDOW_SECONDS = int(os.getenv("DRIFT_WINDOW_SECONDS", "120"))
DRIFT_COOLDOWN_SECONDS = int(os.getenv("DRIFT_COOLDOWN_SECONDS", "600"))

POLL_INTERVAL_SECONDS = float(os.getenv("DRIFT_POLL_INTERVAL_SECONDS", "30"))
RUNTIME_SERVICE_NAME = os.getenv("RUNTIME_SERVICE_NAME", "mlops-drift-monitor")

# Redis key helpers

def _trigger_key(model_name: str) -> str:
    return f"drift:last_trigger_ts:{model_name}"


def _status_key(model_name: str) -> str:
    return f"drift:status:{model_name}"


_DRIFT_EVENTS_LOG_KEY = "drift:events:log"
_MLOPS_REQUEST_INDEX_KEY = "mlops:requests:index"
_MLOPS_REQUEST_PREFIX = "mlops:request:"
_MLOPS_MODEL_PENDING_PREFIX = "mlops:requests:pending:model:"

# metrics ----------------------------------------------------------------------

mlops_drift_anomaly_events_total = Counter(
    "neuroslice_mlops_drift_anomaly_events_total",
    "Total anomaly events observed by mlops-drift-monitor",
    ["model"],
)
mlops_drift_triggers_total = Counter(
    "neuroslice_mlops_drift_triggers_total",
    "Total drift trigger attempts by status",
    ["model", "status"],
)
mlops_drift_last_trigger_timestamp = Gauge(
    "neuroslice_mlops_drift_last_trigger_timestamp",
    "Unix timestamp of the last successful drift trigger",
    ["model"],
)
mlops_drift_enabled = Gauge(
    "neuroslice_mlops_drift_enabled",
    "Whether mlops-drift-monitor request emission is enabled (1) or disabled (0)",
)

# state ------------------------------------------------------------------------

_redis: aioredis.Redis | None = None
_monitor_task: asyncio.Task | None = None
_last_stream_ids: dict[str, str] = {m: "0-0" for m in _MODEL_CONFIG}


class ModelDriftStatus(BaseModel):
    model_name: str
    drift_detected: bool
    anomaly_count: int
    window_seconds: int
    threshold: int
    last_detection_time: str | None
    last_trigger_time: str | None
    pipeline_triggered: bool
    cooldown_active: bool
    pipeline_enabled: bool


# helpers ----------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _now_ts() -> float:
    return time.time()


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    return _redis


def _runtime_key(suffix: str) -> str:
    return f"runtime:service:{RUNTIME_SERVICE_NAME}:{suffix}"


def _parse_bool(value: str | None, *, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


async def _runtime_service_enabled(r: aioredis.Redis) -> bool:
    enabled_raw = await r.get(_runtime_key("enabled"))
    mode = str(await r.get(_runtime_key("mode")) or "").strip().lower()
    enabled = _parse_bool(enabled_raw, default=True)
    if mode == "disabled":
        return False
    return enabled


def _is_real_anomaly(fields: dict, model_name: str) -> bool:
    raw = fields.get("event") or fields.get("payload")
    if not raw:
        return False
    try:
        event = json.loads(raw) if isinstance(raw, str) else raw
        if model_name == "slice_type_5g":
            details = event.get("details") or {}
            if details.get("mismatch") is True:
                return True
            try:
                return int(event.get("severity", 0)) > 0
            except (TypeError, ValueError):
                return False
        allowed = _ANOMALY_PREDICTIONS.get(model_name, set())
        prediction = str(event.get("prediction") or "").lower()
        return prediction in {p.lower() for p in allowed}
    except Exception:
        return False


async def _count_recent_anomalies(r: aioredis.Redis, model_name: str) -> int:
    stream = _MODEL_CONFIG[model_name]["stream"]
    cutoff_ms = int((_now_ts() - DRIFT_WINDOW_SECONDS) * 1000)
    cutoff_id = f"{cutoff_ms}-0"
    try:
        entries = await r.xrange(stream, min=cutoff_id)
        return sum(1 for _, fields in entries if _is_real_anomaly(fields, model_name))
    except Exception as exc:
        logger.warning("[%s] Could not read stream %s: %s", model_name, stream, exc)
        return 0


async def _count_new_anomalies(r: aioredis.Redis, model_name: str) -> int:
    stream = _MODEL_CONFIG[model_name]["stream"]
    last_id = _last_stream_ids.get(model_name, "0-0")
    try:
        chunks = await r.xread({stream: last_id}, count=1000, block=1)
    except Exception:
        return 0

    if not chunks:
        return 0

    total = 0
    for _, messages in chunks:
        if not messages:
            continue
        total += sum(1 for _, fields in messages if _is_real_anomaly(fields, model_name))
        _last_stream_ids[model_name] = messages[-1][0]
    return total


async def _is_in_cooldown(r: aioredis.Redis, model_name: str) -> bool:
    last_ts_str = await r.get(_trigger_key(model_name))
    if last_ts_str is None:
        return False
    try:
        elapsed = _now_ts() - float(last_ts_str)
        return elapsed < DRIFT_COOLDOWN_SECONDS
    except ValueError:
        return False


async def _record_trigger(r: aioredis.Redis, model_name: str) -> None:
    now = _now_ts()
    await r.set(_trigger_key(model_name), str(now))
    mlops_drift_last_trigger_timestamp.labels(model=model_name).set(now)


async def _publish_drift_event(r: aioredis.Redis, model_name: str, anomaly_count: int) -> None:
    payload = {
        "event_type": "drift_detected",
        "model_name": model_name,
        "anomaly_count": str(anomaly_count),
        "window_seconds": str(DRIFT_WINDOW_SECONDS),
        "threshold": str(DRIFT_ANOMALY_THRESHOLD),
        "timestamp": _now_iso(),
    }
    try:
        await r.xadd("events.drift", payload, maxlen=1000)
    except Exception as exc:
        logger.warning("Could not publish drift event: %s", exc)


async def _save_model_status(r: aioredis.Redis, model_name: str, status: dict[str, Any]) -> None:
    try:
        await r.set(_status_key(model_name), json.dumps(status))
        await r.lpush(_DRIFT_EVENTS_LOG_KEY, json.dumps(status))
        await r.ltrim(_DRIFT_EVENTS_LOG_KEY, 0, 99)
    except Exception as exc:
        logger.warning("Could not save drift status for %s: %s", model_name, exc)


async def _has_pending_request(r: aioredis.Redis, model_name: str) -> bool:
    pending_key = f"{_MLOPS_MODEL_PENDING_PREFIX}{model_name}"
    return await r.scard(pending_key) > 0


async def _create_retraining_request(r: aioredis.Redis, model_name: str, anomaly_count: int) -> str:
    request_id = str(uuid.uuid4())
    request = {
        "id": request_id,
        "model": _MODEL_PUBLIC_NAME[model_name],
        "model_internal": model_name,
        "pipeline_action": _MODEL_CONFIG[model_name]["pipeline_action"],
        "reason": "drift_detected",
        "anomaly_count": anomaly_count,
        "threshold": DRIFT_ANOMALY_THRESHOLD,
        "status": "pending_approval",
        "created_at": _now_iso(),
        "approved_by": None,
        "approved_at": None,
        "executed_by": None,
        "executed_at": None,
        "completed_at": None,
        "updated_at": _now_iso(),
        "request_source": "mlops-drift-monitor",
    }

    request_key = f"{_MLOPS_REQUEST_PREFIX}{request_id}"
    pending_key = f"{_MLOPS_MODEL_PENDING_PREFIX}{model_name}"
    await r.set(request_key, json.dumps(request))
    await r.zadd(_MLOPS_REQUEST_INDEX_KEY, {request_id: _now_ts()})
    await r.sadd(pending_key, request_id)

    logger.warning(
        "[%s] DRIFT DETECTED -> approval required (request_id=%s anomaly_count=%d threshold=%d)",
        model_name,
        request_id,
        anomaly_count,
        DRIFT_ANOMALY_THRESHOLD,
    )
    return request_id


async def _trigger_mlops_pipeline(model_name: str, anomaly_count: int) -> bool:
    """Create a retraining request instead of executing training directly."""
    r = await _get_redis()

    if await _has_pending_request(r, model_name):
        logger.info("[%s] Pending approval request already exists - skipping duplicate", model_name)
        mlops_drift_triggers_total.labels(model=model_name, status="pending_exists").inc()
        return False

    await _create_retraining_request(r, model_name, anomaly_count)
    mlops_drift_triggers_total.labels(model=model_name, status="request_created").inc()
    return True


# per-model check --------------------------------------------------------------

async def _check_model(r: aioredis.Redis, model_name: str, monitor_enabled: bool) -> None:
    new_anomalies = await _count_new_anomalies(r, model_name)
    if new_anomalies > 0:
        mlops_drift_anomaly_events_total.labels(model=model_name).inc(new_anomalies)

    anomaly_count = await _count_recent_anomalies(r, model_name)
    drift_detected = anomaly_count >= DRIFT_ANOMALY_THRESHOLD
    cooldown = await _is_in_cooldown(r, model_name)
    pipeline_triggered = False
    last_trigger_str = await r.get(_trigger_key(model_name))
    last_trigger_time = (
        datetime.fromtimestamp(float(last_trigger_str), UTC).isoformat()
        if last_trigger_str else None
    )

    if drift_detected and not cooldown:
        logger.warning(
            "[%s] DRIFT DETECTED - %d anomalies in %ds window. Creating approval request.",
            model_name, anomaly_count, DRIFT_WINDOW_SECONDS,
        )
        await _publish_drift_event(r, model_name, anomaly_count)
        if not monitor_enabled:
            mlops_drift_triggers_total.labels(model=model_name, status="disabled").inc()
        else:
            pipeline_triggered = await _trigger_mlops_pipeline(model_name, anomaly_count)
            if pipeline_triggered:
                await _record_trigger(r, model_name)
                last_trigger_time = _now_iso()
    elif drift_detected and cooldown:
        logger.info("[%s] Drift detected but cooldown active - skipping request", model_name)
        mlops_drift_triggers_total.labels(model=model_name, status="cooldown").inc()

    await _save_model_status(r, model_name, {
        "model_name": model_name,
        "drift_detected": drift_detected,
        "anomaly_count": anomaly_count,
        "window_seconds": DRIFT_WINDOW_SECONDS,
        "threshold": DRIFT_ANOMALY_THRESHOLD,
        "last_detection_time": _now_iso() if drift_detected else None,
        "last_trigger_time": last_trigger_time,
        "pipeline_triggered": pipeline_triggered,
        "cooldown_active": cooldown,
        "pipeline_enabled": monitor_enabled,
        "auto_retrain_enabled": AUTO_RETRAIN_ENABLED,
    })


# monitoring loop --------------------------------------------------------------

async def _monitor_loop() -> None:
    logger.info(
        "Drift monitor started - poll=%ss threshold=%d window=%ds cooldown=%ds models=%s auto_retrain_enabled=%s",
        POLL_INTERVAL_SECONDS, DRIFT_ANOMALY_THRESHOLD, DRIFT_WINDOW_SECONDS,
        DRIFT_COOLDOWN_SECONDS, list(_MODEL_CONFIG), AUTO_RETRAIN_ENABLED,
    )

    r = await _get_redis()
    while True:
        try:
            runtime_enabled = await _runtime_service_enabled(r)
            monitor_enabled = runtime_enabled
            mlops_drift_enabled.set(1 if monitor_enabled else 0)

            for model_name in _MODEL_CONFIG:
                try:
                    await _check_model(r, model_name, monitor_enabled)
                except Exception as exc:
                    logger.error("[%s] Monitor error: %s", model_name, exc)

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Monitor loop error: %s", exc)

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


# API endpoints ----------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    r = await _get_redis()
    redis_ok = False
    runtime_enabled = True
    try:
        await r.ping()
        redis_ok = True
        runtime_enabled = await _runtime_service_enabled(r)
    except Exception:
        pass
    return {
        "status": "ok" if redis_ok else "degraded",
        "service": "drift-monitor",
        "redis": "up" if redis_ok else "down",
        "pipeline_enabled": runtime_enabled,
        "auto_retrain_enabled": AUTO_RETRAIN_ENABLED,
        "models": list(_MODEL_CONFIG),
        "timestamp": _now_iso(),
    }


@app.get("/drift/status")
async def drift_status() -> dict:
    r = await _get_redis()
    runtime_enabled = await _runtime_service_enabled(r)
    result = {}
    for model_name in _MODEL_CONFIG:
        raw = await r.get(_status_key(model_name))
        if raw:
            result[model_name] = json.loads(raw)
        else:
            anomaly_count = await _count_recent_anomalies(r, model_name)
            cooldown = await _is_in_cooldown(r, model_name)
            result[model_name] = ModelDriftStatus(
                model_name=model_name,
                drift_detected=False,
                anomaly_count=anomaly_count,
                window_seconds=DRIFT_WINDOW_SECONDS,
                threshold=DRIFT_ANOMALY_THRESHOLD,
                last_detection_time=None,
                last_trigger_time=None,
                pipeline_triggered=False,
                cooldown_active=cooldown,
                pipeline_enabled=runtime_enabled,
            ).model_dump()
    return result


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/drift/events")
async def drift_events(limit: int = 20) -> dict:
    r = await _get_redis()
    raw_list = await r.lrange(_DRIFT_EVENTS_LOG_KEY, 0, min(limit, 100) - 1)
    events = []
    for raw in raw_list:
        try:
            events.append(json.loads(raw))
        except Exception:
            pass
    return {"count": len(events), "items": events}


@app.post("/drift/trigger")
async def manual_trigger(model_name: str = "congestion_5g") -> dict:
    """Manually create a retraining request for a specific model."""
    if model_name not in _MODEL_CONFIG:
        return {"triggered": False, "reason": f"unknown model '{model_name}'", "valid_models": list(_MODEL_CONFIG)}
    r = await _get_redis()
    runtime_enabled = await _runtime_service_enabled(r)
    anomaly_count = await _count_recent_anomalies(r, model_name)
    cooldown = await _is_in_cooldown(r, model_name)
    if not runtime_enabled:
        mlops_drift_enabled.set(0)
        mlops_drift_triggers_total.labels(model=model_name, status="disabled").inc()
        return {"triggered": False, "reason": "runtime_disabled", "model": model_name, "anomaly_count": anomaly_count}
    if cooldown:
        mlops_drift_triggers_total.labels(model=model_name, status="cooldown").inc()
        return {"triggered": False, "reason": "cooldown_active", "model": model_name, "anomaly_count": anomaly_count}
    await _publish_drift_event(r, model_name, anomaly_count)
    ok = await _trigger_mlops_pipeline(model_name, anomaly_count)
    if ok:
        await _record_trigger(r, model_name)
    return {"triggered": ok, "reason": "manual", "model": model_name, "anomaly_count": anomaly_count}


@app.on_event("startup")
async def startup() -> None:
    global _monitor_task
    r = await _get_redis()
    mlops_drift_enabled.set(0)
    for attempt in range(30):
        try:
            await r.ping()
            logger.info("Connected to Redis")
            runtime_enabled = await _runtime_service_enabled(r)
            mlops_drift_enabled.set(1 if runtime_enabled else 0)
            for model_name in _MODEL_CONFIG:
                last_ts = await r.get(_trigger_key(model_name))
                if last_ts:
                    try:
                        mlops_drift_last_trigger_timestamp.labels(model=model_name).set(float(last_ts))
                    except ValueError:
                        pass
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
