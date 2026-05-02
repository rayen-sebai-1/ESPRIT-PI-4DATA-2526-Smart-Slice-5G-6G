"""Scenario B online evaluator for runtime AIOps predictions."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import deque
from datetime import UTC, datetime
from typing import Any

import redis
import uvicorn
from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("online-evaluator")

SERVICE_NAME = os.getenv("SERVICE_NAME", "online-evaluator")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "7013"))
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

INPUT_TELEMETRY_STREAM = os.getenv("INPUT_TELEMETRY_STREAM", "stream:norm.telemetry")
CONGESTION_STREAM = os.getenv("INPUT_CONGESTION_STREAM", "events.anomaly")
SLA_STREAM = os.getenv("INPUT_SLA_STREAM", "events.sla")
SLICE_STREAM = os.getenv("INPUT_SLICE_STREAM", "events.slice.classification")
EVALUATION_STREAM = os.getenv("OUTPUT_EVALUATION_STREAM", "events.evaluation")

WINDOW_SIZE = int(os.getenv("EVALUATION_WINDOW_SIZE", "500"))
PENDING_TTL_SECONDS = int(os.getenv("EVALUATION_PENDING_TTL_SECONDS", "900"))
READ_BLOCK_MS = int(os.getenv("EVALUATION_READ_BLOCK_MS", "1000"))
READ_COUNT = int(os.getenv("EVALUATION_READ_COUNT", "200"))

MODEL_NAMES = ("congestion_5g", "sla_5g", "slice_type_5g")
MODEL_BY_STREAM = {
    CONGESTION_STREAM: "congestion_5g",
    SLA_STREAM: "sla_5g",
    SLICE_STREAM: "slice_type_5g",
}

EVAL_ACCURACY = Gauge(
    "neuroslice_aiops_eval_accuracy",
    "Rolling online evaluation accuracy",
    ["model_name"],
)
EVAL_PRECISION = Gauge(
    "neuroslice_aiops_eval_precision",
    "Rolling online evaluation precision",
    ["model_name"],
)
EVAL_RECALL = Gauge(
    "neuroslice_aiops_eval_recall",
    "Rolling online evaluation recall",
    ["model_name"],
)
EVAL_F1 = Gauge(
    "neuroslice_aiops_eval_f1",
    "Rolling online evaluation F1 score",
    ["model_name"],
)
EVAL_SAMPLES = Counter(
    "neuroslice_aiops_eval_samples_total",
    "Total evaluated prediction samples",
    ["model_name"],
)

app = FastAPI(title="NeuroSlice Online Evaluator", version="1.0.0")

_redis: redis.Redis | None = None
_task: asyncio.Task | None = None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _encode_hash(data: dict[str, Any]) -> dict[str, str]:
    encoded: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(value, str):
            encoded[key] = value
        else:
            encoded[key] = json.dumps(value)
    return encoded


def _decode_hash(data: dict[str, Any]) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, str):
            try:
                decoded[key] = json.loads(value)
            except Exception:
                decoded[key] = value
        else:
            decoded[key] = value
    return decoded


def _to_bool_prediction(model_name: str, payload: dict[str, Any]) -> bool:
    prediction = str(payload.get("prediction") or "").strip().lower()
    details = payload.get("details")
    if not isinstance(details, dict):
        details = {}

    if model_name == "congestion_5g":
        return prediction in {"congestion_anomaly", "anomaly", "at_risk"}

    if model_name == "sla_5g":
        return prediction in {"sla_at_risk", "risk", "at_risk"}

    mismatch = details.get("mismatch")
    if isinstance(mismatch, bool):
        return mismatch
    observed = str(details.get("observedSliceType") or "").strip()
    predicted = str(payload.get("prediction") or "").strip()
    return bool(observed and predicted and observed != predicted)


class OnlineEvaluator:
    def __init__(self, redis_client: redis.Redis) -> None:
        self.redis = redis_client
        self.pending_predictions: dict[str, dict[str, dict[str, Any]]] = {
            name: {} for name in MODEL_NAMES
        }
        self.history: dict[str, deque[tuple[bool, bool]]] = {
            name: deque(maxlen=WINDOW_SIZE) for name in MODEL_NAMES
        }
        self.samples_total: dict[str, int] = {name: 0 for name in MODEL_NAMES}
        self.last_ids: dict[str, str] = {
            INPUT_TELEMETRY_STREAM: "$",
            CONGESTION_STREAM: "$",
            SLA_STREAM: "$",
            SLICE_STREAM: "$",
        }

    def _active_fault_types(self, entity_id: str | None) -> set[str]:
        fault_types: set[str] = set()
        try:
            raw = self.redis.hgetall("faults:active")
        except Exception:
            return fault_types

        for encoded in raw.values():
            try:
                fault = json.loads(encoded)
            except Exception:
                continue
            ft = str(fault.get("fault_type") or fault.get("faultType") or "").strip()
            if not ft:
                continue
            affected = fault.get("affected_entities") or fault.get("affectedEntities") or []
            if not isinstance(affected, list):
                affected = []
            if not entity_id or not affected or entity_id in affected:
                fault_types.add(ft)
        return fault_types

    def _derive_truth_signals(self, telemetry: dict[str, Any]) -> dict[str, bool]:
        kpis = telemetry.get("kpis")
        if not isinstance(kpis, dict):
            kpis = {}

        derived = telemetry.get("derived")
        if not isinstance(derived, dict):
            derived = {}

        faults = telemetry.get("faults")
        fault_types = set()
        if isinstance(faults, list):
            for item in faults:
                if not isinstance(item, dict):
                    continue
                fault_type = str(item.get("faultType") or item.get("fault_type") or "").strip()
                if fault_type:
                    fault_types.add(fault_type)

        entity_id = str(telemetry.get("entityId") or telemetry.get("entity_id") or "")
        fault_types.update(self._active_fault_types(entity_id))

        scenario_id = str(telemetry.get("scenarioId") or telemetry.get("scenario_id") or "").lower()
        routing = telemetry.get("routing")
        if not isinstance(routing, dict):
            routing = {}

        congestion_score = self._as_float(derived.get("congestionScore") or derived.get("congestion_score"))
        rb_util = self._as_float(kpis.get("rbUtilizationPct") or kpis.get("queueDepthPct"))

        latency_ms = self._as_float(kpis.get("latencyMs") or kpis.get("forwardingLatencyMs"))
        packet_loss_pct = self._as_float(kpis.get("packetLossPct"))
        severity = self._as_int(telemetry.get("severity"))

        routing_mismatch = (
            str(routing.get("expectedUpf") or "") != str(routing.get("actualUpf") or "")
            or str(routing.get("qosProfileExpected") or "") != str(routing.get("qosProfileActual") or "")
        )

        return {
            "congestion_5g": (
                "ran_congestion" in fault_types
                or congestion_score >= 0.7
                or rb_util >= 85.0
            ),
            "sla_5g": (
                bool(
                    fault_types.intersection(
                        {"latency_spike", "packet_loss_spike", "upf_overload", "amf_degradation", "edge_overload"}
                    )
                )
                or severity >= 3
                or latency_ms >= 80.0
                or packet_loss_pct >= 3.0
            ),
            "slice_type_5g": (
                "slice_misrouting" in fault_types
                or "misrouting" in scenario_id
                or routing_mismatch
            ),
        }

    def _compute_metrics(self, model_name: str) -> dict[str, Any]:
        window = self.history[model_name]
        tp = tn = fp = fn = 0
        for predicted, truth in window:
            if predicted and truth:
                tp += 1
            elif predicted and not truth:
                fp += 1
            elif (not predicted) and truth:
                fn += 1
            else:
                tn += 1

        n = len(window)
        accuracy = (tp + tn) / n if n else 0.0
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

        return {
            "model_name": model_name,
            "timestamp": _now_iso(),
            "window_size": n,
            "window_capacity": WINDOW_SIZE,
            "samples_total": self.samples_total[model_name],
            "accuracy": round(float(accuracy), 6),
            "precision": round(float(precision), 6),
            "recall": round(float(recall), 6),
            "f1": round(float(f1), 6),
            "true_positive_count": tp,
            "true_negative_count": tn,
            "false_positive_count": fp,
            "false_negative_count": fn,
            "pseudo_ground_truth_available": n > 0,
        }

    def _persist_metrics(self, metrics: dict[str, Any], source_event_id: str) -> None:
        model_name = str(metrics["model_name"])
        key = f"aiops:evaluation:{model_name}"
        self.redis.hset(key, mapping=_encode_hash(metrics))
        self.redis.sadd("aiops:evaluation:index", model_name)

        event = {
            "event_type": "aiops.evaluation.updated",
            "model_name": model_name,
            "source_event_id": source_event_id,
            "timestamp": metrics["timestamp"],
            "metrics": metrics,
        }
        self.redis.xadd(
            EVALUATION_STREAM,
            {"event": json.dumps(event, separators=(",", ":"), ensure_ascii=True)},
            maxlen=5000,
            approximate=True,
        )

        EVAL_ACCURACY.labels(model_name=model_name).set(float(metrics["accuracy"]))
        EVAL_PRECISION.labels(model_name=model_name).set(float(metrics["precision"]))
        EVAL_RECALL.labels(model_name=model_name).set(float(metrics["recall"]))
        EVAL_F1.labels(model_name=model_name).set(float(metrics["f1"]))

    def _record_prediction(self, stream_name: str, payload: dict[str, Any]) -> None:
        model_name = MODEL_BY_STREAM.get(stream_name)
        if model_name is None:
            return
        source_event_id = str(payload.get("sourceEventId") or payload.get("source_event_id") or "").strip()
        if not source_event_id:
            return

        self.pending_predictions[model_name][source_event_id] = {
            "predicted": _to_bool_prediction(model_name, payload),
            "timestamp": time.time(),
        }

    def _cleanup_pending(self) -> None:
        now = time.time()
        for model_name in MODEL_NAMES:
            stale = [
                key
                for key, row in self.pending_predictions[model_name].items()
                if now - float(row.get("timestamp") or 0.0) > PENDING_TTL_SECONDS
            ]
            for key in stale:
                self.pending_predictions[model_name].pop(key, None)

    @staticmethod
    def _as_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return float(default)
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    @staticmethod
    def _as_int(value: Any, default: int = 0) -> int:
        try:
            if value is None:
                return int(default)
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    def _evaluate_telemetry(self, payload: dict[str, Any]) -> None:
        source_event_id = str(payload.get("eventId") or payload.get("event_id") or "").strip()
        if not source_event_id:
            return

        truths = self._derive_truth_signals(payload)
        for model_name in MODEL_NAMES:
            pending = self.pending_predictions[model_name].pop(source_event_id, None)
            if pending is None:
                continue

            predicted = bool(pending["predicted"])
            truth = bool(truths.get(model_name))
            self.history[model_name].append((predicted, truth))
            self.samples_total[model_name] += 1
            EVAL_SAMPLES.labels(model_name=model_name).inc()

            metrics = self._compute_metrics(model_name)
            self._persist_metrics(metrics, source_event_id)

    @staticmethod
    def _extract_payload(fields: dict[str, Any]) -> dict[str, Any] | None:
        raw = fields.get("event") or fields.get("payload")
        if raw is None:
            return None
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None
        return None

    def _read_latest_state(self, model_name: str) -> dict[str, Any]:
        raw = self.redis.hgetall(f"aiops:evaluation:{model_name}")
        if raw:
            return _decode_hash(raw)
        return {
            "model_name": model_name,
            "status": "no_data",
            "pseudo_ground_truth_available": False,
        }

    async def run_forever(self) -> None:
        logger.info("Online evaluator loop started")
        streams = {
            INPUT_TELEMETRY_STREAM: self.last_ids[INPUT_TELEMETRY_STREAM],
            CONGESTION_STREAM: self.last_ids[CONGESTION_STREAM],
            SLA_STREAM: self.last_ids[SLA_STREAM],
            SLICE_STREAM: self.last_ids[SLICE_STREAM],
        }

        while True:
            try:
                chunks = self.redis.xread(streams, block=READ_BLOCK_MS, count=READ_COUNT)
                if not chunks:
                    await asyncio.sleep(0.05)
                    self._cleanup_pending()
                    continue

                for stream_name, messages in chunks:
                    if not messages:
                        continue
                    stream = str(stream_name)
                    for msg_id, fields in messages:
                        payload = self._extract_payload(fields)
                        if payload is None:
                            continue
                        if stream == INPUT_TELEMETRY_STREAM:
                            self._evaluate_telemetry(payload)
                        else:
                            self._record_prediction(stream, payload)
                        self.last_ids[stream] = msg_id
                        streams[stream] = msg_id

                self._cleanup_pending()

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Evaluator loop error: %s", exc)
                await asyncio.sleep(1.0)

    def latest(self) -> dict[str, Any]:
        models = {name: self._read_latest_state(name) for name in MODEL_NAMES}
        has_data = any(model.get("status") != "no_data" for model in models.values())
        return {
            "models": models,
            "timestamp": _now_iso(),
            "note": None if has_data else "Pseudo-ground-truth not available yet.",
        }

    def latest_model(self, model_name: str) -> dict[str, Any]:
        if model_name not in MODEL_NAMES:
            raise HTTPException(status_code=404, detail=f"Unknown model '{model_name}'.")
        return self._read_latest_state(model_name)

    def recent_events(self, limit: int = 50) -> dict[str, Any]:
        raw = self.redis.xrevrange(EVALUATION_STREAM, count=min(max(limit, 1), 200))
        items: list[dict[str, Any]] = []
        for _, fields in raw:
            payload = self._extract_payload(fields)
            if payload is not None:
                items.append(payload)
        return {"count": len(items), "items": items}


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True,
        )
    return _redis


_evaluator: OnlineEvaluator | None = None


def get_evaluator() -> OnlineEvaluator:
    if _evaluator is None:
        raise HTTPException(status_code=503, detail="online-evaluator not ready")
    return _evaluator


@app.get("/health")
def health() -> dict[str, Any]:
    redis_ok = False
    try:
        _get_redis().ping()
        redis_ok = True
    except Exception:
        pass

    samples = {}
    if _evaluator is not None:
        samples = dict(_evaluator.samples_total)

    return {
        "status": "ok" if redis_ok else "degraded",
        "service": SERVICE_NAME,
        "redis": "up" if redis_ok else "down",
        "samples_total": samples,
        "timestamp": _now_iso(),
    }


@app.get("/evaluation/latest")
def evaluation_latest() -> dict[str, Any]:
    return get_evaluator().latest()


@app.get("/evaluation/latest/{model_name}")
def evaluation_latest_model(model_name: str) -> dict[str, Any]:
    return get_evaluator().latest_model(model_name)


@app.get("/evaluation/events")
def evaluation_events(limit: int = 50) -> dict[str, Any]:
    return get_evaluator().recent_events(limit=limit)


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.on_event("startup")
async def startup() -> None:
    global _evaluator, _task

    for attempt in range(30):
        try:
            r = _get_redis()
            r.ping()
            _evaluator = OnlineEvaluator(r)
            for model_name in MODEL_NAMES:
                EVAL_ACCURACY.labels(model_name=model_name).set(0)
                EVAL_PRECISION.labels(model_name=model_name).set(0)
                EVAL_RECALL.labels(model_name=model_name).set(0)
                EVAL_F1.labels(model_name=model_name).set(0)
            _task = asyncio.create_task(_evaluator.run_forever())
            logger.info("online-evaluator connected to Redis")
            return
        except Exception as exc:
            logger.warning("Waiting for Redis (%d/30): %s", attempt + 1, exc)
            await asyncio.sleep(2.0)

    raise RuntimeError("Could not connect to Redis")


@app.on_event("shutdown")
async def shutdown() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        await asyncio.gather(_task, return_exceptions=True)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT, log_level="info")
