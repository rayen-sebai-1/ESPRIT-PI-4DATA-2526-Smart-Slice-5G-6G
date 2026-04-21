"""
adapter-ves/main.py
VES (Virtual Event Streaming) Adapter Service.

Accepts HTTP POST telemetry events from simulator services,
validates structure, occasionally rejects malformed payloads (5%),
and forwards parsed events to the normalizer via Redis.
Exposes Prometheus /metrics.
"""
from __future__ import annotations

import json
import logging
import random
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import redis
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
import uvicorn

sys.path.insert(0, "/shared")

from shared.config import get_config
from shared.models import RawVesEvent
from shared.redis_client import get_redis, publish_to_stream

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

cfg = get_config()
app = FastAPI(title="neuroslice-sim adapter-ves", version="1.0.0")

# ─────────────────────────────────────────────────────────────────────────────
# Prometheus metrics
# ─────────────────────────────────────────────────────────────────────────────
received_total = Counter("ves_received_total", "Total VES events received")
forwarded_total = Counter("ves_forwarded_total", "Total VES events forwarded")
rejected_total = Counter("ves_rejected_total", "Total VES events rejected (malformed)")
redis_errors_total = Counter("ves_redis_errors_total", "Redis publish error count")

_redis: Optional[redis.Redis] = None

MALFORMED_RATE = float(cfg.__dict__.get("ves_malformed_rate", 0.05))


def get_r() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = get_redis()
    return _redis


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "adapter-ves"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/events", status_code=202)
async def receive_event(request: Request) -> dict:
    received_total.inc()

    body = await request.json()

    # Simulate occasional malformed payload rejection
    if random.random() < MALFORMED_RATE:
        rejected_total.inc()
        publish_to_stream(
            get_r(),
            cfg.stream_raw_ves,
            {"status": "rejected", "reason": "simulated_malformed", "raw": json.dumps(body)},
        )
        raise HTTPException(422, "Simulated malformed payload rejection")

    # Minimal validation
    required_fields = {"source", "domain", "entity_id", "entity_type", "kpis", "timestamp"}
    if not required_fields.issubset(body.keys()):
        rejected_total.inc()
        raise HTTPException(400, f"Missing fields: {required_fields - body.keys()}")

    # Forward to raw VES stream — normalizer picks it up
    try:
        publish_to_stream(get_r(), cfg.stream_raw_ves, {"source": "ves", "payload": json.dumps(body)})
        forwarded_total.inc()
    except Exception as exc:
        redis_errors_total.inc()
        logger.error("Redis error: %s", exc)
        raise HTTPException(503, "Redis unavailable")

    return {"status": "accepted", "entity_id": body.get("entity_id")}


@app.on_event("startup")
async def startup() -> None:
    import asyncio
    for attempt in range(20):
        try:
            r = get_r()
            r.ping()
            logger.info("VES adapter connected to Redis")
            return
        except Exception as exc:
            logger.warning("Waiting for Redis (%d/20): %s", attempt + 1, exc)
            await asyncio.sleep(3)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7001, log_level="info")
