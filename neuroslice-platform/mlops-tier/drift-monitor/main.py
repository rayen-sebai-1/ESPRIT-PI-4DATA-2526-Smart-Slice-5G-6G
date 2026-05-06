"""Drift monitor — human-in-the-loop retraining request creation.

Three sources can create a retraining request (all land as PENDING_APPROVAL):
  1. Anomaly-count threshold exceeded on a Redis stream (original behaviour).
  2. Kafka `drift.alert` message from the aiops-tier statistical detector.
  3. Scheduled cron cycle (configurable interval, never executes automatically).

In every case training is *never* launched here. Requests are written to Redis
and must be approved + executed via the dashboard approval API.
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

app = FastAPI(title="NeuroSlice Drift Monitor", version="3.0.0")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

AUTO_RETRAIN_ENABLED = os.getenv("AUTO_RETRAIN_ENABLED", "false").strip().lower() in {"1", "true", "yes"}

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

# Kafka consumer (drift.alert from aiops-tier statistical monitor)
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_DRIFT_TOPIC = os.getenv("KAFKA_DRIFT_TOPIC", "drift.alert")
KAFKA_CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "mlops-drift-monitor")
KAFKA_CONSUMER_ENABLED = os.getenv("KAFKA_CONSUMER_ENABLED", "true").strip().lower() in {"1", "true", "yes"}
# Only HIGH and CRITICAL severities create a request when coming from Kafka
KAFKA_MIN_SEVERITY = {s.strip().upper() for s in os.getenv("KAFKA_DRIFT_MIN_SEVERITY", "HIGH,CRITICAL").split(",")}

# Scheduled cron retraining
RETRAINING_CRON_ENABLED = os.getenv("RETRAINING_CRON_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
RETRAINING_CRON_EXPR = os.getenv("RETRAINING_CRON_EXPR", "0 2 * * 0")  # Sunday 02:00 by default
RETRAINING_CRON_REQUIRE_APPROVAL = os.getenv("RETRAINING_CRON_REQUIRE_APPROVAL", "true").strip().lower() in {"1", "true", "yes"}
# Comma-separated list of internal model names. Defaults to all known models.
RETRAINING_CRON_MODELS_RAW = os.getenv("RETRAINING_CRON_MODELS", ",".join(_MODEL_CONFIG.keys()))
RETRAINING_CRON_MODELS = [m.strip() for m in RETRAINING_CRON_MODELS_RAW.split(",") if m.strip()]

# ---------------------------------------------------------------------------
# Redis key helpers
# ---------------------------------------------------------------------------

def _trigger_key(model_name: str) -> str:
    return f"drift:last_trigger_ts:{model_name}"


def _status_key(model_name: str) -> str:
    return f"drift:status:{model_name}"


_DRIFT_EVENTS_LOG_KEY = "drift:events:log"
_MLOPS_REQUEST_INDEX_KEY = "mlops:requests:index"
_MLOPS_REQUEST_PREFIX = "mlops:request:"
_MLOPS_MODEL_PENDING_PREFIX = "mlops:requests:pending:model:"
_MLOPS_PENDING_REQUEST_PREFIX = "mlops:requests:pending:request:"
_MLOPS_PENDING_MODEL_LEASE_PREFIX = "mlops:requests:pending:lease:model:"
try:
    _MLOPS_PENDING_TTL_SECONDS = max(
        300,
        int(os.getenv("MLOPS_PENDING_TTL_SECONDS", os.getenv("DRIFT_PENDING_TTL_SECONDS", "7800"))),
    )
except ValueError:
    _MLOPS_PENDING_TTL_SECONDS = 7800

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------

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
mlops_kafka_messages_total = Counter(
    "neuroslice_mlops_kafka_drift_messages_total",
    "Total Kafka drift.alert messages processed by mlops-drift-monitor",
    ["result"],
)
mlops_cron_triggers_total = Counter(
    "neuroslice_mlops_cron_retraining_triggers_total",
    "Total scheduled cron retraining requests created",
    ["model", "status"],
)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_redis: aioredis.Redis | None = None
_monitor_task: asyncio.Task | None = None
_kafka_task: asyncio.Task | None = None
_cron_task: asyncio.Task | None = None
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _now_ts() -> float:
    return time.time()


def _pending_request_key(request_id: str) -> str:
    return f"{_MLOPS_PENDING_REQUEST_PREFIX}{request_id}"


def _pending_model_lease_key(model_name: str) -> str:
    return f"{_MLOPS_PENDING_MODEL_LEASE_PREFIX}{model_name}"


def _safe_iso_to_ts(value: Any) -> float | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.timestamp()


def _load_json_dict(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(str(raw))
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(value, dict):
        return {}
    return value


def _request_trigger_type(raw: dict[str, Any]) -> str:
    value = str(raw.get("trigger_type") or "").strip().upper()
    if value in {"DRIFT", "SCHEDULED", "MANUAL"}:
        return value
    return "DRIFT"


async def _mark_pending_retraining(r: aioredis.Redis, *, model_name: str, request_id: str, owner: str, source: str, created_at: str) -> None:
    created_ts = _safe_iso_to_ts(created_at) or _now_ts()
    expires_ts = created_ts + float(_MLOPS_PENDING_TTL_SECONDS)
    marker = {
        "request_id": request_id,
        "model_name": model_name,
        "created_at": created_at,
        "created_at_epoch": created_ts,
        "expires_at": datetime.fromtimestamp(expires_ts, UTC).isoformat(),
        "expires_at_epoch": expires_ts,
        "owner": owner,
        "source": source,
    }
    await r.sadd(f"{_MLOPS_MODEL_PENDING_PREFIX}{model_name}", request_id)
    await r.set(_pending_request_key(request_id), json.dumps(marker), ex=_MLOPS_PENDING_TTL_SECONDS)
    await r.set(_pending_model_lease_key(model_name), json.dumps(marker), ex=_MLOPS_PENDING_TTL_SECONDS)
    logger.info(
        "[%s] Pending marker created request_id=%s owner=%s source=%s expires_in=%ss",
        model_name,
        request_id,
        owner,
        source,
        _MLOPS_PENDING_TTL_SECONDS,
    )


async def _clear_pending_retraining(r: aioredis.Redis, *, model_name: str, request_id: str, reason: str) -> None:
    pending_key = f"{_MLOPS_MODEL_PENDING_PREFIX}{model_name}"
    lease_key = _pending_model_lease_key(model_name)
    lease_meta = _load_json_dict(await r.get(lease_key))
    lease_request_id = str(lease_meta.get("request_id") or "")
    expires_epoch = lease_meta.get("expires_at_epoch")
    lease_expired = False
    try:
        lease_expired = expires_epoch is not None and float(expires_epoch) <= _now_ts()
    except (TypeError, ValueError):
        lease_expired = False

    await r.srem(pending_key, request_id)
    await r.delete(_pending_request_key(request_id))
    if lease_request_id == request_id or lease_expired or not lease_meta:
        await r.delete(lease_key)
    logger.info("[%s] Pending marker cleared request_id=%s reason=%s", model_name, request_id, reason)


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


async def _has_pending_request(
    r: aioredis.Redis,
    model_name: str,
    *,
    trigger_type: str | None = None,
) -> bool:
    pending_key = f"{_MLOPS_MODEL_PENDING_PREFIX}{model_name}"
    request_ids = list(await r.smembers(pending_key) or [])
    if not request_ids:
        return False

    now_ts = _now_ts()
    live_statuses = {"pending_approval", "approved", "running"}
    terminal_statuses = {"completed", "failed", "skipped", "cancelled", "timeout", "rejected", "expired"}
    has_live = False
    for request_id in request_ids:
        raw = await r.get(f"{_MLOPS_REQUEST_PREFIX}{request_id}")
        if not raw:
            await _clear_pending_retraining(
                r,
                model_name=model_name,
                request_id=str(request_id),
                reason="missing_request_payload",
            )
            continue
        payload = _load_json_dict(raw)
        if not payload:
            await _clear_pending_retraining(
                r,
                model_name=model_name,
                request_id=str(request_id),
                reason="invalid_request_payload",
            )
            continue

        status_value = str(payload.get("status") or "")
        if status_value in terminal_statuses:
            await _clear_pending_retraining(
                r,
                model_name=model_name,
                request_id=str(request_id),
                reason=f"terminal_status:{status_value}",
            )
            continue

        created_ts = _safe_iso_to_ts(payload.get("created_at"))
        if created_ts is not None and (now_ts - created_ts) > float(_MLOPS_PENDING_TTL_SECONDS):
            payload["status"] = "expired"
            payload["completed_at"] = _now_iso()
            payload["execution_detail"] = (
                f"Expired stale pending marker after {int(now_ts - created_ts)} seconds."
            )
            await r.set(f"{_MLOPS_REQUEST_PREFIX}{request_id}", json.dumps(payload))
            await _clear_pending_retraining(
                r,
                model_name=model_name,
                request_id=str(request_id),
                reason="stale_pending_ttl_exceeded",
            )
            continue

        if status_value in live_statuses:
            if trigger_type is None or _request_trigger_type(payload) == trigger_type:
                has_live = True
        else:
            await _clear_pending_retraining(
                r,
                model_name=model_name,
                request_id=str(request_id),
                reason=f"unknown_status:{status_value or 'empty'}",
            )
    return has_live


async def _create_retraining_request(
    r: aioredis.Redis,
    model_name: str,
    *,
    trigger_type: str = "DRIFT",
    anomaly_count: int = 0,
    severity: str | None = None,
    drift_score: float | None = None,
    p_value: float | None = None,
    request_source: str = "mlops-drift-monitor",
    initial_status: str = "pending_approval",
) -> str:
    request_id = str(uuid.uuid4())
    request: dict[str, Any] = {
        "id": request_id,
        "model": _MODEL_PUBLIC_NAME.get(model_name, model_name),
        "model_internal": model_name,
        "pipeline_action": _MODEL_CONFIG.get(model_name, {}).get("pipeline_action", f"pipeline_{model_name}"),
        "trigger_type": trigger_type,
        "reason": "drift_detected" if trigger_type == "DRIFT" else "scheduled",
        "anomaly_count": anomaly_count,
        "threshold": DRIFT_ANOMALY_THRESHOLD,
        "severity": severity,
        "drift_score": drift_score,
        "p_value": p_value,
        "status": initial_status,
        "created_at": _now_iso(),
        "approved_by": None,
        "approved_at": None,
        "executed_by": None,
        "executed_at": None,
        "completed_at": None,
        "updated_at": _now_iso(),
        "request_source": request_source,
    }

    request_key = f"{_MLOPS_REQUEST_PREFIX}{request_id}"
    await r.set(request_key, json.dumps(request))
    await r.zadd(_MLOPS_REQUEST_INDEX_KEY, {request_id: _now_ts()})

    if initial_status == "pending_approval":
        await _mark_pending_retraining(
            r,
            model_name=model_name,
            request_id=request_id,
            owner="mlops-drift-monitor",
            source=request_source,
            created_at=str(request["created_at"]),
        )

    logger.warning(
        "[%s] RETRAINING REQUEST CREATED -> status=%s trigger_type=%s request_id=%s severity=%s p_value=%s",
        model_name,
        initial_status,
        trigger_type,
        request_id,
        severity,
        p_value,
    )
    return request_id


# ---------------------------------------------------------------------------
# Anomaly-stream based drift detection (original behaviour)
# ---------------------------------------------------------------------------

async def _trigger_mlops_pipeline(model_name: str, anomaly_count: int) -> bool:
    """Create a drift retraining request; skip if one is already pending."""
    r = await _get_redis()

    if await _has_pending_request(r, model_name, trigger_type="DRIFT"):
        logger.info("[%s] Pending approval request already exists – skipping duplicate", model_name)
        mlops_drift_triggers_total.labels(model=model_name, status="pending_exists").inc()
        return False

    await _create_retraining_request(
        r,
        model_name,
        trigger_type="DRIFT",
        anomaly_count=anomaly_count,
        request_source="mlops-drift-monitor/anomaly-stream",
    )
    mlops_drift_triggers_total.labels(model=model_name, status="request_created").inc()
    return True


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
            "[%s] DRIFT DETECTED – %d anomalies in %ds window. Creating approval request.",
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
        logger.info("[%s] Drift detected but cooldown active – skipping request", model_name)
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


async def _monitor_loop() -> None:
    logger.info(
        "Anomaly-stream monitor started – poll=%ss threshold=%d window=%ds cooldown=%ds models=%s",
        POLL_INTERVAL_SECONDS, DRIFT_ANOMALY_THRESHOLD, DRIFT_WINDOW_SECONDS,
        DRIFT_COOLDOWN_SECONDS, list(_MODEL_CONFIG),
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


# ---------------------------------------------------------------------------
# Kafka consumer — drift.alert from aiops statistical detector
# ---------------------------------------------------------------------------

async def _kafka_consumer_loop() -> None:
    """Consume drift.alert Kafka events and create retraining requests."""
    # Import inside function so the service can start even if aiokafka isn't
    # installed in environments where Kafka isn't available.
    try:
        from aiokafka import AIOKafkaConsumer  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("aiokafka not installed – Kafka consumer disabled")
        return

    logger.info(
        "Kafka consumer starting – bootstrap=%s topic=%s group=%s min_severity=%s",
        KAFKA_BOOTSTRAP_SERVERS, KAFKA_DRIFT_TOPIC, KAFKA_CONSUMER_GROUP, KAFKA_MIN_SEVERITY,
    )

    consumer: Any = None
    retry_delay = 5.0
    while True:
        try:
            consumer = AIOKafkaConsumer(
                KAFKA_DRIFT_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id=KAFKA_CONSUMER_GROUP,
                auto_offset_reset="latest",
                enable_auto_commit=True,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            )
            await consumer.start()
            retry_delay = 5.0
            logger.info("Kafka consumer connected to %s", KAFKA_BOOTSTRAP_SERVERS)

            async for msg in consumer:
                try:
                    await _handle_kafka_drift_event(msg.value)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.error("Error handling Kafka drift event: %s", exc)
                    mlops_kafka_messages_total.labels(result="error").inc()

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("Kafka consumer error (retry in %ss): %s", retry_delay, exc)
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 120.0)
        finally:
            if consumer is not None:
                try:
                    await consumer.stop()
                except Exception:
                    pass
                consumer = None


async def _handle_kafka_drift_event(event: Any) -> None:
    """Process one drift.alert message; create a retraining request if criteria met."""
    if not isinstance(event, dict):
        mlops_kafka_messages_total.labels(result="invalid").inc()
        return

    is_drift = bool(event.get("is_drift"))
    if not is_drift:
        mlops_kafka_messages_total.labels(result="no_drift").inc()
        return

    severity = str(event.get("severity") or "").strip().upper()
    if severity not in KAFKA_MIN_SEVERITY:
        logger.info(
            "Kafka drift event ignored – severity=%s not in required set %s",
            severity, KAFKA_MIN_SEVERITY,
        )
        mlops_kafka_messages_total.labels(result="severity_filtered").inc()
        return

    auto_trigger = bool(event.get("auto_trigger_enabled", False))
    if not auto_trigger:
        logger.info(
            "Kafka drift event: auto_trigger_enabled=false – request blocked by design (human-in-loop)"
        )
        mlops_kafka_messages_total.labels(result="auto_trigger_off").inc()
        return

    model_name_raw = str(event.get("model_name") or "").strip()
    # Accept both internal (congestion_5g) and canonical names
    if model_name_raw not in _MODEL_CONFIG:
        # try reverse-map from public name
        _reverse = {v: k for k, v in _MODEL_PUBLIC_NAME.items()}
        model_name_raw = _reverse.get(model_name_raw, model_name_raw)
    if model_name_raw not in _MODEL_CONFIG:
        logger.warning("Kafka drift event: unknown model_name '%s' – skipped", model_name_raw)
        mlops_kafka_messages_total.labels(result="unknown_model").inc()
        return

    r = await _get_redis()

    runtime_enabled = await _runtime_service_enabled(r)
    if not runtime_enabled:
        logger.info("[%s] Kafka drift event – runtime disabled, skipping request", model_name_raw)
        mlops_kafka_messages_total.labels(result="runtime_disabled").inc()
        return

    if await _is_in_cooldown(r, model_name_raw):
        logger.info("[%s] Kafka drift event – cooldown active, skipping request", model_name_raw)
        mlops_kafka_messages_total.labels(result="cooldown").inc()
        return

    if await _has_pending_request(r, model_name_raw, trigger_type="DRIFT"):
        logger.info("[%s] Kafka drift event – pending request already exists, skipping duplicate", model_name_raw)
        mlops_kafka_messages_total.labels(result="duplicate").inc()
        return

    p_value_raw = event.get("p_value")
    p_value = float(p_value_raw) if p_value_raw is not None else None
    drift_score_raw = event.get("drift_score")
    drift_score = float(drift_score_raw) if drift_score_raw is not None else None
    window_size = int(event.get("window_size") or 0)

    await _create_retraining_request(
        r,
        model_name_raw,
        trigger_type="DRIFT",
        anomaly_count=window_size,
        severity=severity,
        drift_score=drift_score,
        p_value=p_value,
        request_source="kafka/drift.alert",
        initial_status="pending_approval",
    )
    await _record_trigger(r, model_name_raw)
    mlops_kafka_messages_total.labels(result="request_created").inc()
    mlops_drift_triggers_total.labels(model=model_name_raw, status="kafka_request_created").inc()


# ---------------------------------------------------------------------------
# Scheduled cron retraining
# ---------------------------------------------------------------------------

def _seconds_until_next_cron(cron_expr: str) -> float:
    """Return seconds until the next scheduled firing for a cron expression."""
    try:
        from croniter import croniter  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("croniter not installed – using 24h fallback")
        return 86400.0

    base = datetime.now(UTC)
    it = croniter(cron_expr, base)
    nxt = it.get_next(datetime)
    diff = (nxt - base).total_seconds()
    return max(diff, 1.0)


async def _cron_scheduler_loop() -> None:
    """Fire scheduled retraining requests on the configured cron expression."""
    logger.info(
        "Cron scheduler started – expr=%r require_approval=%s models=%s",
        RETRAINING_CRON_EXPR, RETRAINING_CRON_REQUIRE_APPROVAL, RETRAINING_CRON_MODELS,
    )

    while True:
        try:
            wait_sec = _seconds_until_next_cron(RETRAINING_CRON_EXPR)
            logger.info("Cron scheduler: next fire in %.0f seconds", wait_sec)
            await asyncio.sleep(wait_sec)
        except asyncio.CancelledError:
            raise

        try:
            await _fire_scheduled_retraining()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Cron scheduler error during fire: %s", exc)


async def _fire_scheduled_retraining() -> None:
    """Create scheduled retraining requests for all configured models."""
    r = await _get_redis()
    runtime_enabled = await _runtime_service_enabled(r)

    for model_name in RETRAINING_CRON_MODELS:
        if model_name not in _MODEL_CONFIG:
            logger.warning("Cron: skipping unknown model '%s'", model_name)
            continue
        try:
            await _create_scheduled_request(r, model_name, runtime_enabled)
        except Exception as exc:
            logger.error("[%s] Cron: failed to create request: %s", model_name, exc)


async def _create_scheduled_request(r: aioredis.Redis, model_name: str, runtime_enabled: bool) -> None:
    if await _has_pending_request(r, model_name, trigger_type="SCHEDULED"):
        logger.info("[%s] Cron: pending request exists – skipping duplicate", model_name)
        mlops_cron_triggers_total.labels(model=model_name, status="duplicate").inc()
        return

    if not runtime_enabled:
        logger.info("[%s] Cron: runtime disabled – skipping", model_name)
        mlops_cron_triggers_total.labels(model=model_name, status="runtime_disabled").inc()
        return

    # Respect same cooldown as drift triggers to avoid spam
    if await _is_in_cooldown(r, model_name):
        logger.info("[%s] Cron: cooldown active – skipping", model_name)
        mlops_cron_triggers_total.labels(model=model_name, status="cooldown").inc()
        return

    if RETRAINING_CRON_REQUIRE_APPROVAL:
        initial_status = "pending_approval"
    else:
        # Cron with approval disabled goes straight to approved; execution
        # still must be triggered explicitly via the API.
        initial_status = "approved"

    await _create_retraining_request(
        r,
        model_name,
        trigger_type="SCHEDULED",
        request_source="cron-scheduler",
        initial_status=initial_status,
    )
    await _record_trigger(r, model_name)
    mlops_cron_triggers_total.labels(model=model_name, status="request_created").inc()
    logger.info(
        "[%s] Cron: scheduled retraining request created – status=%s require_approval=%s",
        model_name, initial_status, RETRAINING_CRON_REQUIRE_APPROVAL,
    )


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

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
        "kafka_consumer_enabled": KAFKA_CONSUMER_ENABLED,
        "kafka_topic": KAFKA_DRIFT_TOPIC,
        "cron_enabled": RETRAINING_CRON_ENABLED,
        "cron_expr": RETRAINING_CRON_EXPR if RETRAINING_CRON_ENABLED else None,
        "cron_require_approval": RETRAINING_CRON_REQUIRE_APPROVAL,
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
    """Manually create a retraining request (trigger_type=DRIFT) for testing."""
    if model_name not in _MODEL_CONFIG:
        return {"triggered": False, "reason": f"unknown model '{model_name}'", "valid_models": list(_MODEL_CONFIG)}
    r = await _get_redis()
    runtime_enabled = await _runtime_service_enabled(r)
    anomaly_count = await _count_recent_anomalies(r, model_name)
    cooldown = await _is_in_cooldown(r, model_name)
    if not runtime_enabled:
        mlops_drift_enabled.set(0)
        mlops_drift_triggers_total.labels(model=model_name, status="disabled").inc()
        return {"triggered": False, "reason": "runtime_disabled", "model": model_name}
    if cooldown:
        mlops_drift_triggers_total.labels(model=model_name, status="cooldown").inc()
        return {"triggered": False, "reason": "cooldown_active", "model": model_name}
    await _publish_drift_event(r, model_name, anomaly_count)
    ok = await _trigger_mlops_pipeline(model_name, anomaly_count)
    if ok:
        await _record_trigger(r, model_name)
    return {"triggered": ok, "reason": "manual", "model": model_name, "anomaly_count": anomaly_count}


@app.post("/retraining/scheduled/trigger")
async def trigger_scheduled_now(model_name: str | None = None) -> dict:
    """Manually fire the scheduled retraining cycle (useful for testing)."""
    r = await _get_redis()
    runtime_enabled = await _runtime_service_enabled(r)
    models = [model_name] if model_name else RETRAINING_CRON_MODELS
    created = []
    skipped = []
    for m in models:
        if m not in _MODEL_CONFIG:
            skipped.append({"model": m, "reason": "unknown"})
            continue
        try:
            if await _has_pending_request(r, m, trigger_type="SCHEDULED"):
                skipped.append({"model": m, "reason": "pending_exists"})
            elif await _is_in_cooldown(r, m):
                skipped.append({"model": m, "reason": "cooldown"})
            else:
                initial_status = "pending_approval" if RETRAINING_CRON_REQUIRE_APPROVAL else "approved"
                req_id = await _create_retraining_request(
                    r, m, trigger_type="SCHEDULED", request_source="manual/scheduled-trigger",
                    initial_status=initial_status,
                )
                await _record_trigger(r, m)
                mlops_cron_triggers_total.labels(model=m, status="request_created").inc()
                created.append({"model": m, "request_id": req_id, "status": initial_status})
        except Exception as exc:
            skipped.append({"model": m, "reason": str(exc)})
    return {"created": created, "skipped": skipped, "runtime_enabled": runtime_enabled}


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup() -> None:
    global _monitor_task, _kafka_task, _cron_task
    r = await _get_redis()
    mlops_drift_enabled.set(0)

    for attempt in range(30):
        try:
            await r.ping()
            logger.info("Connected to Redis")
            runtime_enabled = await _runtime_service_enabled(r)
            mlops_drift_enabled.set(1 if runtime_enabled else 0)
            for model_name in _MODEL_CONFIG:
                await _has_pending_request(r, model_name)
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

    if KAFKA_CONSUMER_ENABLED:
        _kafka_task = asyncio.create_task(_kafka_consumer_loop())
        logger.info("Kafka consumer task started – topic=%s", KAFKA_DRIFT_TOPIC)
    else:
        logger.info("Kafka consumer disabled (KAFKA_CONSUMER_ENABLED=false)")

    if RETRAINING_CRON_ENABLED:
        _cron_task = asyncio.create_task(_cron_scheduler_loop())
        logger.info(
            "Cron scheduler task started – expr=%r models=%s require_approval=%s",
            RETRAINING_CRON_EXPR, RETRAINING_CRON_MODELS, RETRAINING_CRON_REQUIRE_APPROVAL,
        )
    else:
        logger.info("Cron scheduler disabled (RETRAINING_CRON_ENABLED=false)")


@app.on_event("shutdown")
async def shutdown() -> None:
    for task in (_monitor_task, _kafka_task, _cron_task):
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
