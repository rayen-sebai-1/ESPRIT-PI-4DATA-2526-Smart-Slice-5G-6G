"""Bridge Logstash events into the canonical Redis telemetry stream."""
from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

import redis
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

sys.path.insert(0, "/shared")

from shared.redis_client import get_redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("logstash-aiops-ingest")

SERVICE_NAME = os.getenv("SERVICE_NAME", "logstash-aiops-ingest")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "7014"))
DEFAULT_SITE_ID = os.getenv("SITE_ID", "TT-SFAX-02")
OUTPUT_STREAM = os.getenv("OUTPUT_STREAM", "stream:norm.telemetry")
STREAM_MAXLEN = int(os.getenv("STREAM_MAXLEN", "10000"))
MAX_EVENT_AGE_SECONDS = int(os.getenv("LOGSTASH_EVENT_MAX_AGE_SECONDS", "900"))

app = FastAPI(title="NeuroSlice Logstash AIOps Ingest", version="1.0.0")
_redis: redis.Redis | None = None


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _ensure_iso8601(value: str) -> str:
    if not value:
        return _utcnow().isoformat()
    text = str(value).strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text).astimezone(UTC).isoformat()
    except ValueError:
        return _utcnow().isoformat()


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _decode_kpis(value: Any) -> dict[str, float]:
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    if not isinstance(value, dict):
        return {}
    out: dict[str, float] = {}
    for key, raw in value.items():
        number = _to_float(raw)
        if number is not None:
            out[str(key)] = number
    return out


class LogstashIngestEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    event_id: str = Field(alias="event_id")
    timestamp: str
    source_service: str
    slice_id: str | None = None
    cell_id: str | None = None
    gnb_id: str | None = None
    metric_name: str | None = None
    metric_value: float | None = None
    anomaly_score: float | None = None
    prediction: str | None = None
    site_id: str | None = None
    domain: str | None = None
    entity_id: str | None = None
    entity_type: str | None = None
    kpis: dict[str, Any] | str | None = None
    payload: dict[str, Any] | None = None

    @field_validator("event_id")
    @classmethod
    def _non_empty_event_id(cls, value: str) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("event_id must not be empty")
        return text

    @field_validator("source_service")
    @classmethod
    def _non_empty_source_service(cls, value: str) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("source_service must not be empty")
        return text

    @field_validator("timestamp")
    @classmethod
    def _valid_timestamp(cls, value: str) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("timestamp must not be empty")
        ts = text[:-1] + "+00:00" if text.endswith("Z") else text
        try:
            datetime.fromisoformat(ts)
        except ValueError as exc:
            raise ValueError("timestamp must be ISO-8601") from exc
        return text

    @model_validator(mode="after")
    def _has_observable_signal(self) -> "LogstashIngestEvent":
        has_signal = any(
            (
                self.metric_name,
                self.metric_value is not None,
                self.anomaly_score is not None,
                self.prediction,
                bool(_decode_kpis(self.kpis)),
            )
        )
        if not has_signal:
            raise ValueError(
                "event must contain at least one of metric_name/metric_value/anomaly_score/prediction/kpis"
            )
        return self


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = get_redis()
    return _redis


def _derive_entity(event: LogstashIngestEvent) -> tuple[str, str, str]:
    entity_id = (
        event.entity_id
        or event.cell_id
        or event.gnb_id
        or event.slice_id
        or f"{event.source_service}-unknown"
    )
    if event.entity_type:
        entity_type = event.entity_type
    elif event.cell_id:
        entity_type = "cell"
    elif event.gnb_id:
        entity_type = "gnb"
    else:
        entity_type = "gnb"
    node_id = event.gnb_id or event.cell_id or entity_id
    return entity_id, entity_type, node_id


def _derive_kpis(event: LogstashIngestEvent) -> dict[str, float]:
    kpis = _decode_kpis(event.kpis)
    metric_name = (event.metric_name or "").strip()
    if metric_name and event.metric_value is not None:
        kpis[metric_name] = float(event.metric_value)
    if event.metric_value is not None and "metricValue" not in kpis:
        kpis["metricValue"] = float(event.metric_value)
    return kpis


def _derive_derived(event: LogstashIngestEvent) -> dict[str, float]:
    derived = {
        "congestionScore": 0.0,
        "healthScore": 1.0,
        "misroutingScore": 0.0,
    }
    if event.anomaly_score is not None:
        score = max(0.0, min(1.0, float(event.anomaly_score)))
        derived["congestionScore"] = score
        derived["healthScore"] = max(0.0, 1.0 - score)
    return derived


def _severity_from_score(score: float) -> int:
    if score < 0.3:
        return 0
    if score < 0.5:
        return 1
    if score < 0.7:
        return 2
    if score < 0.85:
        return 3
    return 4


def _canonical_event(event: LogstashIngestEvent, freshness_seconds: float) -> dict[str, Any]:
    entity_id, entity_type, node_id = _derive_entity(event)
    derived = _derive_derived(event)
    congestion_score = float(derived["congestionScore"])
    extra = event.model_extra or {}
    payload = event.payload or {}
    return {
        "eventId": event.event_id or str(uuid.uuid4()),
        "timestamp": _ensure_iso8601(event.timestamp),
        "domain": (event.domain or "ran").lower(),
        "siteId": event.site_id or DEFAULT_SITE_ID,
        "nodeId": node_id,
        "entityId": entity_id,
        "entityType": entity_type,
        "sliceId": event.slice_id,
        "sliceType": payload.get("slice_type") or payload.get("sliceType"),
        "protocol": "internal",
        "vendor": "logstash",
        "kpis": _derive_kpis(event),
        "derived": derived,
        "routing": payload.get("routing"),
        "faults": [],
        "scenarioId": "logstash_realtime",
        "severity": _severity_from_score(congestion_score),
        "sourceService": event.source_service,
        "prediction": event.prediction,
        "metricName": event.metric_name,
        "metricValue": event.metric_value,
        "anomalyScore": event.anomaly_score,
        "freshnessSeconds": round(float(freshness_seconds), 3),
        "sourcePayload": payload,
        "logstashMeta": {
            "eventDataset": extra.get("[event][dataset]") or extra.get("event", {}).get("dataset"),
            "ingestTimestamp": _utcnow().isoformat(),
        },
    }


def _event_freshness_seconds(timestamp: str) -> float:
    parsed = datetime.fromisoformat(_ensure_iso8601(timestamp))
    return (_utcnow() - parsed).total_seconds()


@app.get("/health")
def health() -> dict[str, Any]:
    redis_ok = False
    try:
        _get_redis().ping()
        redis_ok = True
    except Exception:
        pass
    return {
        "status": "ok" if redis_ok else "degraded",
        "service": SERVICE_NAME,
        "redis": "up" if redis_ok else "down",
        "output_stream": OUTPUT_STREAM,
        "timestamp": _utcnow().isoformat(),
    }


@app.post("/ingest/logstash", status_code=202)
def ingest_logstash_event(raw_event: dict[str, Any]) -> dict[str, Any]:
    try:
        event = LogstashIngestEvent.model_validate(raw_event)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_logstash_event",
                "message": "Event does not match the Logstash->AIOps contract.",
                "issues": exc.errors(),
            },
        ) from exc

    freshness_seconds = _event_freshness_seconds(event.timestamp)
    if freshness_seconds > MAX_EVENT_AGE_SECONDS:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "stale_event",
                "message": (
                    f"Event timestamp is stale by {freshness_seconds:.3f}s "
                    f"(max={MAX_EVENT_AGE_SECONDS}s)."
                ),
                "event_id": event.event_id,
                "source_service": event.source_service,
                "timestamp": event.timestamp,
            },
        )

    canonical = _canonical_event(event, freshness_seconds=freshness_seconds)

    logger.info(
        "model_receive %s",
        json.dumps(
            {
                "event_id": canonical["eventId"],
                "slice_id": canonical.get("sliceId"),
                "timestamp": canonical["timestamp"],
                "source_service": event.source_service,
                "freshness_seconds": round(float(freshness_seconds), 3),
            },
            separators=(",", ":"),
            ensure_ascii=True,
        ),
    )

    try:
        message_id = _get_redis().xadd(
            OUTPUT_STREAM,
            {"event": json.dumps(canonical, separators=(",", ":"), ensure_ascii=True)},
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "redis_unavailable",
                "message": f"Failed publishing event to {OUTPUT_STREAM}: {exc}",
            },
        ) from exc

    logger.info(
        "model_receive_forwarded %s",
        json.dumps(
            {
                "event_id": canonical["eventId"],
                "stream": OUTPUT_STREAM,
                "stream_id": message_id,
                "slice_id": canonical.get("sliceId"),
                "timestamp": canonical["timestamp"],
                "source_service": event.source_service,
            },
            separators=(",", ":"),
            ensure_ascii=True,
        ),
    )
    return {
        "status": "accepted",
        "stream": OUTPUT_STREAM,
        "stream_id": message_id,
        "event_id": canonical["eventId"],
        "freshness_seconds": round(float(freshness_seconds), 3),
    }


@app.on_event("startup")
async def startup() -> None:
    import asyncio

    for attempt in range(20):
        try:
            r = _get_redis()
            r.ping()
            logger.info("Connected to Redis stream=%s", OUTPUT_STREAM)
            return
        except Exception as exc:
            logger.warning("Waiting for Redis (%d/20): %s", attempt + 1, exc)
            await asyncio.sleep(2)
    raise RuntimeError("Could not connect to Redis")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT, log_level="info")
