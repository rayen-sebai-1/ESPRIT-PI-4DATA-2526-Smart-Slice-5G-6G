"""Online inference logic for congestion-detector."""
from __future__ import annotations

import logging
import math
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Deque, Dict, List, Tuple

import numpy as np

from config import CongestionConfig
from model_loader import CongestionModelBundle
from schemas import CanonicalTelemetryEvent, CongestionOutputEvent
from shared.onnx_runtime import run_session

logger = logging.getLogger(__name__)


class CongestionInferencer:
    def __init__(self, cfg: CongestionConfig, bundle: CongestionModelBundle) -> None:
        self.cfg = cfg
        self.bundle = bundle
        self.sequence_length = max(2, bundle.sequence_length)
        self.threshold = float(cfg.congestion_threshold)
        self._buffers: Dict[str, Deque[List[float]]] = defaultdict(
            lambda: deque(maxlen=self.sequence_length)
        )

    def update_bundle(self, bundle: CongestionModelBundle) -> None:
        old_sequence = self.sequence_length
        self.bundle = bundle
        self.sequence_length = max(2, bundle.sequence_length)

        if self.sequence_length != old_sequence:
            previous = self._buffers
            self._buffers = defaultdict(lambda: deque(maxlen=self.sequence_length))
            for key, values in previous.items():
                self._buffers[key].extend(list(values)[-self.sequence_length :])

        logger.info(
            "Updated congestion model bundle: version=%s format=%s source=%s",
            bundle.model_version,
            bundle.model_format,
            bundle.model_source,
        )

    def infer(self, raw_event: Dict[str, Any]) -> CongestionOutputEvent | None:
        event = CanonicalTelemetryEvent.model_validate(raw_event)

        feature_row = self._feature_row(event)
        key = event.slice_id or event.entity_id
        buffer = self._buffers[key]
        buffer.append(feature_row)

        score, model_used, reason = self._predict_score(event, list(buffer))
        score = max(0.0, min(1.0, float(score)))

        prediction = "congestion_anomaly" if score >= self.threshold else "normal"
        severity = self._severity(score)

        return CongestionOutputEvent(
            service=self.cfg.service_name,
            siteId=event.site_id or self.cfg.default_site_id,
            sliceId=event.slice_id,
            entityId=event.entity_id,
            entityType=event.entity_type,
            severity=severity,
            score=round(score, 6),
            prediction=prediction,
            modelVersion=self.bundle.model_version,
            sourceEventId=event.event_id,
            domain=event.domain,
            explanation=reason,
            details={
                "threshold": self.threshold,
                "modelLoaded": self.bundle.loaded,
                "modelUsed": model_used,
                "modelFormat": self.bundle.model_format,
                "fallbackMode": self.bundle.fallback_mode,
                "onnxruntimeEnabled": self.bundle.onnxruntime_enabled,
                "bufferLength": len(buffer),
                "reason": reason,
                "scenarioId": event.scenario_id,
            },
        )

    def _predict_score(
        self, event: CanonicalTelemetryEvent, sequence: List[List[float]]
    ) -> Tuple[float, bool, str]:
        if self.bundle.model is None:
            return self._heuristic_score(event), False, "model_unavailable"

        if len(sequence) < self.sequence_length:
            return self._heuristic_score(event), False, "sequence_not_ready"

        try:
            seq_array = np.asarray(sequence[-self.sequence_length :], dtype=np.float32)
            if self.bundle.preprocessor is not None and hasattr(self.bundle.preprocessor, "scaler"):
                seq_array = self.bundle.preprocessor.scaler.transform(seq_array)

            if self.bundle.model_format == "onnx_fp16":
                outputs = run_session(self.bundle.model, seq_array[np.newaxis, ...])
                raw_score = float(np.asarray(outputs[0]).squeeze())
            else:
                import torch

                tensor = torch.tensor(seq_array, dtype=torch.float32).unsqueeze(0)
                with torch.no_grad():
                    raw_out = self.bundle.model(tensor)
                raw_score = float(raw_out.squeeze().item())

            # Model was trained with BCE-with-logits. Convert logits -> probability.
            return 1.0 / (1.0 + math.exp(-raw_score)), True, "model_inference"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Congestion model inference failed, fallback to heuristic: %s", exc)
            return self._heuristic_score(event), False, "model_inference_failed"

    def _feature_row(self, event: CanonicalTelemetryEvent) -> List[float]:
        kpis = event.kpis or {}
        derived = event.derived or {}

        cpu = self._as_float(kpis.get("cpuUtilPct"), default=self._as_float(derived.get("congestionScore")) * 100.0)
        mem = self._as_float(kpis.get("memUtilPct"), default=cpu * 0.8)
        bw = self._as_float(
            kpis.get("rbUtilizationPct"),
            default=self._as_float(kpis.get("queueDepthPct"), default=self._as_float(derived.get("congestionScore")) * 100.0),
        )
        active_users = self._as_float(
            kpis.get("ueCount"),
            default=self._as_float(kpis.get("activeUeCount"), default=self._as_float(kpis.get("activeSessions"))),
        )
        queue_len = self._as_float(
            kpis.get("registrationQueueLen"),
            default=self._as_float(kpis.get("pduSetupQueueLen"), default=self._as_float(kpis.get("queueDepthPct"))),
        )
        hour = float(self._event_hour(event.timestamp))
        slice_type_encoded = float(self._slice_type_to_encoded(event.slice_type))

        return [cpu, mem, bw, active_users, queue_len, hour, slice_type_encoded]

    def _slice_type_to_encoded(self, slice_type: str | None) -> int:
        if not slice_type:
            return -1

        if self.bundle.preprocessor is not None and hasattr(self.bundle.preprocessor, "le"):
            try:
                return int(self.bundle.preprocessor.le.transform([slice_type])[0])
            except Exception:  # noqa: BLE001
                pass

        fallback = {"eMBB": 0, "URLLC": 1, "mMTC": 2}
        return fallback.get(slice_type, -1)

    def _heuristic_score(self, event: CanonicalTelemetryEvent) -> float:
        kpis = event.kpis or {}
        derived = event.derived or {}

        if "congestionScore" in derived:
            return self._as_float(derived.get("congestionScore"))

        cpu = self._as_float(kpis.get("cpuUtilPct")) / 100.0
        mem = self._as_float(kpis.get("memUtilPct")) / 100.0
        bw = self._as_float(kpis.get("rbUtilizationPct"), default=self._as_float(kpis.get("queueDepthPct"))) / 100.0
        pkt_loss = self._as_float(kpis.get("packetLossPct")) / 100.0
        queue = self._as_float(kpis.get("registrationQueueLen"), default=self._as_float(kpis.get("pduSetupQueueLen")))
        queue_norm = min(queue / 100.0, 1.0)

        return max(0.0, min(1.0, 0.45 * bw + 0.25 * cpu + 0.15 * mem + 0.1 * queue_norm + 0.05 * pkt_loss))

    @staticmethod
    def _severity(score: float) -> int:
        if score < 0.3:
            return 0
        if score < 0.5:
            return 1
        if score < 0.7:
            return 2
        if score < 0.85:
            return 3
        return 4

    @staticmethod
    def _event_hour(timestamp: str) -> int:
        if not timestamp:
            return datetime.utcnow().hour
        try:
            ts = timestamp.replace("Z", "+00:00")
            return datetime.fromisoformat(ts).hour
        except Exception:  # noqa: BLE001
            return datetime.utcnow().hour

    @staticmethod
    def _as_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return float(default)
            return float(value)
        except (TypeError, ValueError):
            return float(default)
