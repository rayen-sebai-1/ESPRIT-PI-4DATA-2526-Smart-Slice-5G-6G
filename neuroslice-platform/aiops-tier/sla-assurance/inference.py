"""Online inference logic for sla-assurance."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

import numpy as np

from config import SlaAssuranceConfig
from model_loader import SlaModelBundle
from schemas import CanonicalTelemetryEvent, SlaEvent

logger = logging.getLogger(__name__)


class SlaInferencer:
    def __init__(self, cfg: SlaAssuranceConfig, bundle: SlaModelBundle) -> None:
        self.cfg = cfg
        self.bundle = bundle

    def infer(self, raw_event: Dict[str, Any]) -> SlaEvent | None:
        event = CanonicalTelemetryEvent.model_validate(raw_event)
        feature_vec = self._feature_vector(event)

        risk_score, sla_probability, model_used = self._predict(feature_vec, event)
        risk_score = max(0.0, min(1.0, float(risk_score)))
        sla_probability = max(0.0, min(1.0, float(sla_probability)))

        prediction = "sla_at_risk" if risk_score >= self.cfg.sla_risk_threshold else "sla_stable"
        severity = self._severity(risk_score)

        return SlaEvent(
            service=self.cfg.service_name,
            siteId=event.site_id or self.cfg.default_site_id,
            sliceId=event.slice_id,
            entityId=event.entity_id,
            entityType=event.entity_type,
            severity=severity,
            score=round(risk_score, 6),
            prediction=prediction,
            modelVersion=self.bundle.model_version,
            sourceEventId=event.event_id,
            details={
                "slaProbability": round(sla_probability, 6),
                "riskThreshold": self.cfg.sla_risk_threshold,
                "modelLoaded": self.bundle.loaded,
                "modelUsed": model_used,
                "modelFormat": self.bundle.model_format,
                "fallbackMode": self.bundle.fallback_mode,
                "onnxruntimeEnabled": self.bundle.onnxruntime_enabled,
                "featureVector": feature_vec,
                "scenarioId": event.scenario_id,
            },
        )

    def _predict(
        self, feature_vec: List[float], event: CanonicalTelemetryEvent
    ) -> Tuple[float, float, bool]:
        model = self.bundle.model
        scaler = self.bundle.scaler

        if model is not None and scaler is not None:
            try:
                features = np.asarray([feature_vec], dtype=np.float32)
                features_scaled = scaler.transform(features)
                probabilities = model.predict_proba(features_scaled)[0]
                sla_probability = float(probabilities[1])
                risk_score = 1.0 - sla_probability
                return risk_score, sla_probability, True
            except Exception as exc:  # noqa: BLE001
                logger.warning("SLA model inference failed, using heuristic fallback: %s", exc)

        risk_score = self._heuristic_risk(event)
        return risk_score, 1.0 - risk_score, False

    def _feature_vector(self, event: CanonicalTelemetryEvent) -> List[float]:
        kpis = event.kpis or {}

        packet_loss = self._as_float(kpis.get("packetLossPct"))
        packet_delay = self._as_float(
            kpis.get("latencyMs"),
            default=self._as_float(kpis.get("forwardingLatencyMs"), default=20.0),
        )

        observed = (event.slice_type or "").lower()
        smart_city_home = 1.0 if observed == "mmtc" else 0.0
        iot_devices = 1.0 if observed == "mmtc" else 0.0
        public_safety = 1.0 if observed == "urllc" else 0.0

        # Match preprocess_sla_5g.py feature order.
        return [packet_loss, packet_delay, smart_city_home, iot_devices, public_safety]

    def _heuristic_risk(self, event: CanonicalTelemetryEvent) -> float:
        kpis = event.kpis or {}
        derived = event.derived or {}

        packet_loss = self._as_float(kpis.get("packetLossPct"))
        packet_delay = self._as_float(
            kpis.get("latencyMs"),
            default=self._as_float(kpis.get("forwardingLatencyMs"), default=20.0),
        )
        congestion = self._as_float(derived.get("congestionScore"))

        loss_norm = min(packet_loss / 10.0, 1.0)
        delay_norm = min(packet_delay / 100.0, 1.0)
        return max(0.0, min(1.0, 0.5 * delay_norm + 0.3 * loss_norm + 0.2 * congestion))

    @staticmethod
    def _severity(risk_score: float) -> int:
        if risk_score < 0.2:
            return 0
        if risk_score < 0.4:
            return 1
        if risk_score < 0.6:
            return 2
        if risk_score < 0.8:
            return 3
        return 4

    @staticmethod
    def _as_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return float(default)
            return float(value)
        except (TypeError, ValueError):
            return float(default)
