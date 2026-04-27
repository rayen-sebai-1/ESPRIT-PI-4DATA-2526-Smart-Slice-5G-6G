"""Online inference logic for slice-classifier."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

import numpy as np

from config import SliceClassifierConfig
from model_loader import SliceModelBundle
from schemas import CanonicalTelemetryEvent, SliceClassificationEvent

logger = logging.getLogger(__name__)


class SliceInferencer:
    def __init__(self, cfg: SliceClassifierConfig, bundle: SliceModelBundle) -> None:
        self.cfg = cfg
        self.bundle = bundle

    def update_bundle(self, bundle: SliceModelBundle) -> None:
        self.bundle = bundle
        logger.info(
            "Updated slice model bundle: version=%s format=%s source=%s",
            bundle.model_version,
            bundle.model_format,
            bundle.model_source,
        )

    def infer(self, raw_event: Dict[str, Any]) -> SliceClassificationEvent | None:
        event = CanonicalTelemetryEvent.model_validate(raw_event)
        feature_vec = self._feature_vector(event)

        prediction, confidence, probabilities, model_used = self._predict(feature_vec)
        observed_slice = event.slice_type
        mismatch = bool(observed_slice and prediction != observed_slice)
        severity = self._severity(mismatch, confidence)

        return SliceClassificationEvent(
            service=self.cfg.service_name,
            siteId=event.site_id or self.cfg.default_site_id,
            sliceId=event.slice_id,
            entityId=event.entity_id,
            entityType=event.entity_type,
            severity=severity,
            score=round(confidence, 6),
            prediction=prediction,
            modelVersion=self.bundle.model_version,
            sourceEventId=event.event_id,
            domain=event.domain,
            explanation=None,
            details={
                "observedSliceType": observed_slice,
                "mismatch": mismatch,
                "modelLoaded": self.bundle.loaded,
                "modelUsed": model_used,
                "modelFormat": self.bundle.model_format,
                "fallbackMode": self.bundle.fallback_mode,
                "onnxruntimeEnabled": self.bundle.onnxruntime_enabled,
                "featureVector": feature_vec,
                "probabilities": probabilities,
                "scenarioId": event.scenario_id,
            },
        )

    def _predict(self, feature_vec: List[float]) -> Tuple[str, float, Dict[str, float], bool]:
        model = self.bundle.model
        encoder = self.bundle.label_encoder

        if model is not None and encoder is not None:
            try:
                features = np.array([feature_vec], dtype=np.float32)
                probabilities = model.predict_proba(features)[0]
                label = int(np.argmax(probabilities))
                predicted = str(encoder.inverse_transform([label])[0])
                confidence = float(probabilities[label])

                class_names = [str(v) for v in encoder.classes_]
                proba_map = {
                    cls: round(float(probabilities[idx]), 6)
                    for idx, cls in enumerate(class_names)
                    if idx < len(probabilities)
                }
                return predicted, confidence, proba_map, True
            except Exception as exc:  # noqa: BLE001
                logger.warning("Slice model inference failed, using heuristic fallback: %s", exc)

        predicted, confidence = self._heuristic(feature_vec)
        return predicted, confidence, {}, False

    def _heuristic(self, feature_vec: List[float]) -> Tuple[str, float]:
        _, packet_loss, packet_delay, smartphone, iot_devices, gbr = feature_vec

        if packet_delay <= 20.0 and packet_loss <= 1.0:
            return "URLLC", 0.72
        if iot_devices >= 0.5 and gbr < 0.5:
            return "mMTC", 0.68
        if smartphone >= 0.5:
            return "eMBB", 0.66
        return "eMBB", 0.55

    def _feature_vector(self, event: CanonicalTelemetryEvent) -> List[float]:
        kpis = event.kpis or {}
        derived = event.derived or {}

        packet_loss = self._as_float(kpis.get("packetLossPct"), default=self._as_float(derived.get("congestionScore")) * 2.0)
        packet_delay = self._as_float(
            kpis.get("latencyMs"),
            default=self._as_float(kpis.get("forwardingLatencyMs"), default=15.0),
        )

        throughput = self._as_float(kpis.get("dlThroughputMbps"), default=self._as_float(kpis.get("throughputMbps")))
        ue_count = self._as_float(kpis.get("ueCount"), default=self._as_float(kpis.get("activeUeCount")))

        observed = (event.slice_type or "").lower()
        smartphone = 1.0 if observed == "embb" or throughput >= 150.0 else 0.0
        iot_devices = 1.0 if observed == "mmtc" or ue_count >= 250.0 else 0.0
        gbr = 1.0 if observed in {"embb", "urllc"} or packet_delay < 25.0 else 0.0

        # Match the training order from preprocess_slice_type_5g.py.
        return [2.0, packet_loss, packet_delay, smartphone, iot_devices, gbr]

    def _severity(self, mismatch: bool, confidence: float) -> int:
        if not mismatch:
            return 0
        if confidence >= self.cfg.mismatch_confidence_threshold:
            return 3
        if confidence >= 0.6:
            return 2
        return 1

    @staticmethod
    def _as_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return float(default)
            return float(value)
        except (TypeError, ValueError):
            return float(default)
