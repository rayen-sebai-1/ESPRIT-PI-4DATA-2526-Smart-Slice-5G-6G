from __future__ import annotations

from packages.neuroslice_common.enums import RiskLevel, SliceType
from packages.neuroslice_common.models import NetworkSession, Region
from packages.neuroslice_common.prediction_common import (
    PredictionResult,
    clamp,
    compute_risk_level,
    decimal_to_float,
)


class MockPredictionProvider:
    name = "mock-telecom-heuristic"
    version = "1.0.0"

    def predict(self, session: NetworkSession, region: Region) -> PredictionResult:
        latency = decimal_to_float(session.latency_ms)
        packet_loss = decimal_to_float(session.packet_loss)
        throughput = decimal_to_float(session.throughput_mbps)
        network_load = decimal_to_float(region.network_load)

        latency_penalty = clamp(latency / 90.0, 0.0, 1.0)
        packet_loss_penalty = clamp(packet_loss / 4.0, 0.0, 1.0)
        load_penalty = clamp(network_load / 100.0, 0.0, 1.0)
        throughput_penalty = 1.0 - clamp(throughput / 900.0, 0.0, 1.0)

        sla_score = clamp(
            1.0 - (0.42 * latency_penalty + 0.33 * packet_loss_penalty + 0.25 * load_penalty),
            0.05,
            0.99,
        )
        congestion_score = clamp(
            0.58 * load_penalty + 0.27 * latency_penalty + 0.15 * (1.0 - throughput_penalty),
            0.02,
            0.99,
        )
        anomaly_score = clamp(
            0.50 * packet_loss_penalty + 0.25 * latency_penalty + 0.25 * abs(load_penalty - throughput_penalty),
            0.01,
            0.98,
        )

        predicted_slice_type = self._infer_slice_type(session, latency, packet_loss, throughput, network_load)
        slice_confidence = clamp(0.55 + (sla_score * 0.25) + ((1.0 - anomaly_score) * 0.20), 0.40, 0.99)
        risk_level = compute_risk_level(sla_score, congestion_score, anomaly_score)
        recommended_action = self._recommend_action(risk_level, latency, packet_loss, network_load)

        return PredictionResult(
            sla_score=round(sla_score, 4),
            congestion_score=round(congestion_score, 4),
            anomaly_score=round(anomaly_score, 4),
            risk_level=risk_level,
            predicted_slice_type=predicted_slice_type,
            slice_confidence=round(slice_confidence, 4),
            recommended_action=recommended_action,
            model_source=f"{self.name}:{self.version}",
        )

    def _infer_slice_type(
        self,
        session: NetworkSession,
        latency: float,
        packet_loss: float,
        throughput: float,
        network_load: float,
    ) -> SliceType:
        if latency <= 8 and packet_loss <= 0.4:
            return SliceType.ERLLC if throughput >= 350 else SliceType.URLLC
        if throughput >= 500:
            return SliceType.FEMBB if latency < 25 else SliceType.EMBB
        if throughput <= 80 and packet_loss <= 1.2:
            return SliceType.UMMTC if network_load < 55 else SliceType.MMTC
        if latency <= 15 and throughput >= 250:
            return SliceType.MURLLC
        if throughput >= 300:
            return SliceType.MBRLLC
        return session.slice_type

    def _recommend_action(
        self,
        risk_level: RiskLevel,
        latency: float,
        packet_loss: float,
        network_load: float,
    ) -> str:
        if risk_level is RiskLevel.CRITICAL:
            return "Escalader immediatement, reaffecter la slice critique et soulager la region saturee."
        if risk_level is RiskLevel.HIGH and network_load >= 75:
            return "Declencher un reequilibrage de charge inter-gNodeB et renforcer la capacite radio locale."
        if risk_level is RiskLevel.HIGH and packet_loss >= 1.5:
            return "Inspecter le transport IP et verifier un possible misrouting ou une degradation du backhaul."
        if risk_level is RiskLevel.MEDIUM and latency >= 30:
            return "Surveiller la latence et preparer une reallocation proactive avant degradation SLA."
        return "Maintenir la session sous surveillance standard et poursuivre l observation des KPI."
