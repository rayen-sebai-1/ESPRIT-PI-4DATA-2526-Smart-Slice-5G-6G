"""FastAPI entrypoint for the drift-monitor service.

Exposes:
  GET /health
  GET /drift/latest
  GET /drift/latest/{model_name}
  GET /drift/events
  GET /metrics   (Prometheus)

Background tasks:
  - Redis stream consumer (reads stream:norm.telemetry)
  - Periodic Alibi Detect MMD drift tests (every DRIFT_TEST_INTERVAL_SEC)
  - Prometheus metric updater
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Gauge, make_asgi_app

from config import get_config
from consumer import DriftConsumer
from drift_store import DriftStore
from redis_client import get_redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("drift-monitor")

cfg = get_config()

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------

drift_window_size_g = Gauge(
    "neuroslice_drift_window_size", "Rolling window sample count", ["model_name"]
)
drift_p_value_g = Gauge(
    "neuroslice_drift_p_value", "Latest p-value from drift test", ["model_name"]
)
drift_detected_c = Counter(
    "neuroslice_drift_detected_total", "Total drift detections emitted", ["model_name"]
)
drift_reference_loaded_g = Gauge(
    "neuroslice_drift_reference_loaded", "1 if reference artifact loaded", ["model_name"]
)
drift_last_check_ts_g = Gauge(
    "neuroslice_drift_last_check_timestamp",
    "Unix timestamp of last drift check",
    ["model_name"],
)
drift_events_emitted_c = Counter(
    "neuroslice_drift_events_emitted_total",
    "Total drift alert events published",
    ["model_name"],
)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="drift-monitor",
    description="Alibi Detect MMD drift monitor for Scenario B",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/metrics", make_asgi_app())

_consumer: Optional[DriftConsumer] = None
_store: Optional[DriftStore] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> Dict[str, Any]:
    redis_ok = False
    try:
        get_redis().ping()
        redis_ok = True
    except Exception:  # noqa: BLE001
        pass

    model_statuses: Dict[str, str] = {}
    if _consumer:
        for name in cfg.drift_model_names:
            model_statuses[name] = _consumer.get_model_status(name).status

    all_degraded = bool(model_statuses) and all(
        s in ("reference_missing", "alibi_unavailable") for s in model_statuses.values()
    )
    overall = "degraded" if (not redis_ok or all_degraded) else "ok"

    return {
        "status": overall,
        "service": cfg.service_name,
        "redis": "up" if redis_ok else "down",
        "models": model_statuses,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/drift/latest")
def get_drift_latest() -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for name in cfg.drift_model_names:
        state = _store.get_state(name) if _store else None
        if state is None and _consumer:
            state = _consumer.get_model_status(name).model_dump()
        result[name] = state or {"model_name": name, "status": "no_data"}
    return {"models": result, "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/drift/latest/{model_name}")
def get_drift_latest_model(model_name: str) -> Dict[str, Any]:
    if model_name not in cfg.drift_model_names:
        raise HTTPException(
            404,
            f"Unknown model '{model_name}'. Known: {cfg.drift_model_names}",
        )
    state = _store.get_state(model_name) if _store else None
    if state is None and _consumer:
        return _consumer.get_model_status(model_name).model_dump()
    return state or {"model_name": model_name, "status": "no_data"}


@app.get("/drift/events")
def get_drift_events(limit: int = 50) -> Dict[str, Any]:
    if _store is None:
        return {"events": [], "count": 0}
    events = _store.read_recent_events(count=min(limit, 200))
    return {"events": events, "count": len(events)}


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def startup() -> None:
    global _consumer, _store

    for attempt in range(30):
        try:
            get_redis().ping()
            logger.info("Connected to Redis")
            break
        except Exception as exc:  # noqa: BLE001
            logger.warning("Waiting for Redis (%d/30): %s", attempt + 1, exc)
            await asyncio.sleep(2)

    _store = DriftStore(get_redis())
    _consumer = DriftConsumer(cfg, _store)

    for name in cfg.drift_model_names:
        st = _consumer.get_model_status(name)
        drift_reference_loaded_g.labels(model_name=name).set(1 if st.reference_loaded else 0)
        drift_window_size_g.labels(model_name=name).set(0)

    asyncio.create_task(_run_consumer())
    asyncio.create_task(_run_drift_tests())
    asyncio.create_task(_run_metric_updater())

    logger.info("drift-monitor startup complete. Monitoring: %s", cfg.drift_model_names)


async def _run_consumer() -> None:
    assert _consumer is not None
    try:
        await _consumer.run_forever()
    except Exception as exc:  # noqa: BLE001
        logger.error("Consumer task crashed: %s", exc)


async def _run_drift_tests() -> None:
    assert _consumer is not None
    try:
        await _consumer.run_drift_tests()
    except Exception as exc:  # noqa: BLE001
        logger.error("Drift test task crashed: %s", exc)


async def _run_metric_updater() -> None:
    while True:
        await asyncio.sleep(30)
        if _store is None or _consumer is None:
            continue
        for name in cfg.drift_model_names:
            try:
                state = _store.get_state(name)
                if not state:
                    continue
                p_val = state.get("p_value")
                if p_val is not None:
                    drift_p_value_g.labels(model_name=name).set(float(p_val))
                drift_window_size_g.labels(model_name=name).set(
                    int(state.get("window_size") or 0)
                )
                drift_last_check_ts_g.labels(model_name=name).set(
                    datetime.now(timezone.utc).timestamp()
                )
                drift_reference_loaded_g.labels(model_name=name).set(
                    1 if state.get("reference_loaded") else 0
                )
                if state.get("is_drift"):
                    drift_detected_c.labels(model_name=name).inc(0)
                    drift_events_emitted_c.labels(model_name=name).inc(0)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Metric update failed for %s: %s", name, exc)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=cfg.service_port, log_level="info")
