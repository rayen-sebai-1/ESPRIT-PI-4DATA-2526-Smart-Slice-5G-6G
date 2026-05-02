"""Background Redis stream consumer and periodic drift test runner."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

import numpy as np

from alibi_detector import ModelDriftDetector
from config import DriftConfig
from drift_store import DriftStore
from feature_extractor import FEATURE_SCHEMAS, extract_features
from influx_client import get_write_api, write_drift_point
from kafka_client import get_producer, publish
from schemas import DriftEvent, DriftState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _severity_for_p_val(p_val: float) -> str:
    if p_val < 0.001:
        return "CRITICAL"
    if p_val < 0.005:
        return "HIGH"
    if p_val < 0.01:
        return "MEDIUM"
    return "LOW"


def _recommendation(model_name: str, severity: str) -> str:
    if severity in ("CRITICAL", "HIGH"):
        return (
            f"Run offline MLOps pipeline and compare candidate model quality gates. "
            f"Review feature distribution shift for {model_name}. "
            f"Do not auto-promote without operator review."
        )
    return (
        f"Review feature distribution shift for {model_name}. "
        f"Consider running the MLOps pipeline for {model_name}."
    )


# ---------------------------------------------------------------------------
# DriftConsumer
# ---------------------------------------------------------------------------


class DriftConsumer:
    """Consumes stream:norm.telemetry, accumulates rolling windows per model,
    and runs periodic MMD drift tests via Alibi Detect."""

    def __init__(self, cfg: DriftConfig, store: DriftStore) -> None:
        self.cfg = cfg
        self.store = store

        self._windows: Dict[str, Deque[List[float]]] = {
            name: deque(maxlen=cfg.drift_window_size * 2)
            for name in cfg.drift_model_names
        }

        self._detectors: Dict[str, ModelDriftDetector] = {
            name: ModelDriftDetector(
                model_name=name,
                models_base_path=cfg.models_base_path,
                p_val=cfg.drift_p_value_threshold,
                window_size=cfg.drift_window_size,
            )
            for name in cfg.drift_model_names
        }

        self._last_emit: Dict[str, float] = {}
        self._running = False

        self._kafka_producer = get_producer(cfg.kafka_broker)
        self._write_api = get_write_api(
            cfg.influxdb_url, cfg.influxdb_token, cfg.influxdb_org
        )

    # ------------------------------------------------------------------
    # Public status
    # ------------------------------------------------------------------

    def get_model_status(self, model_name: str) -> DriftState:
        detector = self._detectors.get(model_name)
        window = self._windows.get(model_name, deque())
        schema = FEATURE_SCHEMAS.get(model_name, {})

        if detector is None:
            return DriftState(model_name=model_name, status="no_data")

        det_status = detector.status
        # Map detector status to public status when no drift run yet
        if det_status == "ready":
            public_status = "insufficient_data"
        else:
            public_status = det_status

        return DriftState(
            model_name=model_name,
            status=public_status,
            deployment_version=detector.deployment_version,
            window_size=len(window),
            window_capacity=self.cfg.drift_window_size,
            reference_sample_count=detector.reference_sample_count,
            reference_loaded=detector.x_ref is not None,
            threshold=self.cfg.drift_p_value_threshold,
            feature_names=detector.feature_names or schema.get("feature_names", []),
            auto_trigger_enabled=self.cfg.drift_auto_trigger_mlops,
        )

    # ------------------------------------------------------------------
    # Consumer loop
    # ------------------------------------------------------------------

    async def run_forever(self) -> None:
        import redis as redis_module

        from redis_client import get_redis

        r = get_redis()
        try:
            r.xgroup_create(
                self.cfg.input_stream, self.cfg.consumer_group, id="$", mkstream=True
            )
        except redis_module.exceptions.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

        logger.info(
            "Drift consumer starting: stream=%s group=%s consumer=%s",
            self.cfg.input_stream,
            self.cfg.consumer_group,
            self.cfg.consumer_name,
        )

        self._running = True
        while self._running:
            try:
                if not self._is_runtime_enabled(r):
                    await asyncio.sleep(0.5)
                    continue
                raw = r.xreadgroup(
                    self.cfg.consumer_group,
                    self.cfg.consumer_name,
                    {self.cfg.input_stream: ">"},
                    count=self.cfg.read_count,
                    block=self.cfg.block_ms,
                )
                if not raw:
                    await asyncio.sleep(0.05)
                    continue

                for _stream, messages in raw:
                    for msg_id, fields in messages:
                        try:
                            self._process_message(fields)
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("Message processing failed %s: %s", msg_id, exc)
                        finally:
                            r.xack(self.cfg.input_stream, self.cfg.consumer_group, msg_id)

            except Exception as exc:  # noqa: BLE001
                logger.warning("Consumer loop error: %s", exc)
                await asyncio.sleep(1.0)

    def _process_message(self, fields: Dict[str, Any]) -> None:
        raw = fields.get("event") or fields.get("payload")
        if raw is None:
            return
        if isinstance(raw, str):
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                return
        elif isinstance(raw, dict):
            event = raw
        else:
            return

        for model_name in self.cfg.drift_model_names:
            feat = extract_features(event, model_name)
            if feat is not None:
                self._windows[model_name].append(feat)

    # ------------------------------------------------------------------
    # Drift test loop
    # ------------------------------------------------------------------

    async def run_drift_tests(self) -> None:
        """Background periodic drift test; runs independently of consumer loop."""
        from redis_client import get_redis

        r = get_redis()
        while True:
            await asyncio.sleep(self.cfg.drift_test_interval_sec)
            if not self._is_runtime_enabled(r):
                continue
            now = time.monotonic()
            for model_name in self.cfg.drift_model_names:
                try:
                    self._run_drift_test(model_name, now)
                except Exception as exc:  # noqa: BLE001
                    logger.error("Drift test error for %s: %s", model_name, exc)

    def _run_drift_test(self, model_name: str, now: float) -> None:
        window = self._windows.get(model_name, deque())
        detector = self._detectors.get(model_name)
        if detector is None:
            return

        x_live = (
            np.asarray(list(window), dtype=np.float32)
            if window
            else np.empty((0, 1), dtype=np.float32)
        )

        result = detector.run(x_live)

        status = result.get("status", "error")
        is_drift = bool(result.get("is_drift", False))
        p_val: Optional[float] = result.get("p_val")
        drift_score: Optional[float] = result.get("drift_score")
        severity = _severity_for_p_val(p_val) if (is_drift and p_val is not None) else "NONE"
        recommendation = _recommendation(model_name, severity) if is_drift else ""

        schema = FEATURE_SCHEMAS.get(model_name, {})
        feature_names = detector.feature_names or schema.get("feature_names", [])

        state = DriftState(
            model_name=model_name,
            status=status,
            deployment_version=detector.deployment_version,
            window_size=len(window),
            window_capacity=self.cfg.drift_window_size,
            reference_sample_count=detector.reference_sample_count,
            reference_loaded=detector.x_ref is not None,
            p_value=p_val,
            threshold=self.cfg.drift_p_value_threshold,
            is_drift=is_drift,
            drift_score=drift_score,
            feature_names=feature_names,
            severity=severity,
            recommendation=recommendation,
            last_checked_at=datetime.now(timezone.utc).isoformat(),
            last_drift_at=datetime.now(timezone.utc).isoformat() if is_drift else None,
            auto_trigger_enabled=self.cfg.drift_auto_trigger_mlops,
        )

        self.store.save_state(state)

        write_drift_point(
            self._write_api,
            self.cfg.influxdb_bucket,
            self.cfg.influxdb_org,
            model_name,
            {
                "is_drift": is_drift,
                "p_val": p_val,
                "drift_score": drift_score,
                "severity": severity,
                "window_size": len(window),
                "reference_sample_count": detector.reference_sample_count,
            },
        )

        if is_drift:
            cooldown_elapsed = now - self._last_emit.get(model_name, 0.0)
            if cooldown_elapsed >= self.cfg.drift_emit_cooldown_sec:
                self._emit_drift_event(
                    model_name, state, p_val, drift_score, severity, recommendation, feature_names
                )
                self._last_emit[model_name] = now

    def _emit_drift_event(
        self,
        model_name: str,
        state: DriftState,
        p_val: float,
        drift_score: Optional[float],
        severity: str,
        recommendation: str,
        feature_names: List[str],
    ) -> None:
        event = DriftEvent(
            model_name=model_name,
            deployment_version=state.deployment_version,
            window_size=state.window_size,
            reference_sample_count=state.reference_sample_count,
            p_value=p_val,
            threshold=self.cfg.drift_p_value_threshold,
            is_drift=True,
            drift_score=drift_score,
            feature_names=feature_names,
            severity=severity,
            recommendation=recommendation,
            auto_trigger_enabled=self.cfg.drift_auto_trigger_mlops,
        )

        event_data = event.model_dump()
        self.store.publish_drift_event(event_data)
        publish(self._kafka_producer, self.cfg.kafka_drift_topic, event_data)

        logger.warning(
            "DRIFT DETECTED: model=%s p_val=%.4f severity=%s drift_id=%s",
            model_name,
            p_val,
            severity,
            event.drift_id,
        )

    def _is_runtime_enabled(self, r) -> bool:
        enabled_raw = r.get(self._runtime_key("enabled"))
        mode = str(r.get(self._runtime_key("mode")) or "").strip().lower()
        enabled = self._parse_bool(enabled_raw, default=True)
        if mode == "disabled":
            return False
        return enabled

    def _runtime_key(self, suffix: str) -> str:
        return f"runtime:service:{self.cfg.runtime_service_name}:{suffix}"

    @staticmethod
    def _parse_bool(value: Any, default: bool = True) -> bool:
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
