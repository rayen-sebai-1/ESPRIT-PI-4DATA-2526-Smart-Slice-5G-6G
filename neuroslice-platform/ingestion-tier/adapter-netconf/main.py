"""
adapter-netconf/main.py
NETCONF/YANG-style Adapter Service.

Simulates NETCONF subscription-style telemetry ingestion.
Receives hierarchical telemetry blobs from simulator-edge,
transforms to flat records, occasionally introduces schema mismatches,
and forwards to Redis for normalizer consumption.
"""
from __future__ import annotations

import json
import logging
import random
import sys
from typing import Any, Dict, Optional

import redis
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
import uvicorn

sys.path.insert(0, "/shared")

from shared.config import get_config
from shared.redis_client import get_redis, publish_to_stream

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

cfg = get_config()
app = FastAPI(title="neuroslice-sim adapter-netconf", version="1.0.0")

received_total = Counter("netconf_received_total", "Telemetry blobs received")
forwarded_total = Counter("netconf_forwarded_total", "Events forwarded after flattening")
schema_mismatch_total = Counter("netconf_schema_mismatch_total", "Simulated schema mismatches")
redis_errors_total = Counter("netconf_redis_errors_total", "Redis errors")

_redis: Optional[redis.Redis] = None
SCHEMA_MISMATCH_RATE = 0.03  # 3% schema mismatch rate


def get_r() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = get_redis()
    return _redis


def flatten_netconf(blob: dict) -> list[dict]:
    """
    Transform hierarchical NETCONF-like data to a list of flat records.
    Each top-level key under 'data' becomes a separate record.
    """
    flat = []
    metadata = blob.get("data", {}).get("metadata", {})
    for section_key, section_data in blob.get("data", {}).items():
        if section_key == "metadata":
            continue
        record = {
            "source": blob.get("source", "unknown"),
            "managed_element": blob.get("managed_element", "unknown"),
            "timestamp": blob.get("timestamp"),
            "schema_version": blob.get("schema_version", "1.0"),
            "scenario_id": blob.get("scenario_id", "normal_day"),
            "section": section_key,
            **metadata,
        }
        # Flatten one level of section data
        if isinstance(section_data, dict):
            record.update(section_data)
        flat.append(record)
    return flat


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "adapter-netconf"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/telemetry", status_code=202)
async def receive_telemetry(request: Request) -> dict:
    received_total.inc()
    blob = await request.json()

    # Simulate schema mismatch — rename a field to cause downstream confusion
    if random.random() < SCHEMA_MISMATCH_RATE:
        schema_mismatch_total.inc()
        # Introduce a known mismatch (delay_ms vs latencyMs)
        data = blob.get("data", {})
        for section in data.values():
            if isinstance(section, dict) and "forwardingLatencyMs" in section:
                section["delay_ms"] = section.pop("forwardingLatencyMs")  # wrong field name
        blob["schema_version"] = "1.1-MISMATCH"
        logger.warning("Schema mismatch injected for %s", blob.get("managed_element"))

    flat_records = flatten_netconf(blob)
    for record in flat_records:
        try:
            publish_to_stream(
                get_r(),
                cfg.stream_raw_netconf,
                {"source": "netconf", "payload": json.dumps(record)},
            )
            forwarded_total.inc()
        except Exception as exc:
            redis_errors_total.inc()
            logger.error("Redis error: %s", exc)

    return {"status": "accepted", "records": len(flat_records)}


@app.on_event("startup")
async def startup() -> None:
    import asyncio
    for attempt in range(20):
        try:
            get_r().ping()
            logger.info("NETCONF adapter connected to Redis")
            return
        except Exception as exc:
            logger.warning("Waiting for Redis (%d/20): %s", attempt + 1, exc)
            await asyncio.sleep(3)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7002, log_level="info")
