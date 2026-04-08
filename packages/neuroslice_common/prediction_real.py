from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

from packages.neuroslice_common.models import NetworkSession
from packages.neuroslice_common.prediction_common import (
    ANOMALY_FEATURES,
    ANOMALY_SLICE_ALIASES,
    CONGESTION_FEATURES,
    CONGESTION_SLICE_ALIASES,
    SLA_FEATURES,
    SLICE_CLASS_TO_RUNTIME,
    SLICE_FEATURES,
    AnomalyEvaluation,
    ModelDescriptor,
    clamp,
    decimal_to_float,
    normalize_decision_score,
    normalize_packet_delay,
    normalize_packet_loss,
    normalize_slice_class,
)


class LightGBMBoosterRuntime:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.feature_names = [str(name) for name in payload.get("feature_names", [])]
        self.tree_info = list(payload.get("tree_info", []))
        self.num_class = max(int(payload.get("num_class", 1)), 1)
        self.num_tree_per_iteration = max(int(payload.get("num_tree_per_iteration", self.num_class)), 1)

    def predict_proba(self, row: dict[str, float]) -> list[float]:
        ordered_values = [float(row.get(feature_name, 0.0)) for feature_name in self.feature_names]
        raw_scores = [0.0 for _ in range(self.num_class)]

        for tree in self.tree_info:
            class_index = int(tree.get("class_index", int(tree.get("tree_index", 0)) % self.num_tree_per_iteration))
            raw_scores[class_index] += self._evaluate_tree(tree["tree_structure"], ordered_values)

        max_score = max(raw_scores)
        exp_scores = [math.exp(score - max_score) for score in raw_scores]
        total = sum(exp_scores) or 1.0
        return [score / total for score in exp_scores]

    def _evaluate_tree(self, node: dict[str, Any], ordered_values: list[float]) -> float:
        if "leaf_value" in node:
            return float(node["leaf_value"])

        feature_index = int(node["split_feature"])
        feature_value = ordered_values[feature_index] if feature_index < len(ordered_values) else 0.0
        branch = "left_child" if self._go_left(feature_value, node) else "right_child"
        return self._evaluate_tree(node[branch], ordered_values)

    def _go_left(self, feature_value: float, node: dict[str, Any]) -> bool:
        if math.isnan(feature_value):
            return bool(node.get("default_left", True))

        decision_type = str(node.get("decision_type", "<="))
        threshold = float(node.get("threshold", 0.0))

        if decision_type == "<=":
            return feature_value <= threshold
        if decision_type == "<":
            return feature_value < threshold
        if decision_type == "==":
            return feature_value == threshold
        if decision_type == "!=":
            return feature_value != threshold

        raise ValueError(f"Unsupported LightGBM decision type: {decision_type}")


class RealSLABoostingProvider:
    name = "sla-boosting-adapter"
    version = "1.1.0"

    def __init__(self, *, model_path: str, scaler_path: str, metadata_path: str) -> None:
        self.model_path = Path(model_path)
        self.scaler_path = Path(scaler_path)
        self.metadata_path = Path(metadata_path)
        self._model: Any = None
        self._scaler: Any = None
        self._metadata: dict[str, Any] = {}
        self.error_message: str | None = None
        self.available = False
        self._load_artifacts()

    @property
    def artifact_root(self) -> str:
        return self.model_path.parent.as_posix()

    def _load_artifacts(self) -> None:
        if not (self.model_path.exists() and self.scaler_path.exists() and self.metadata_path.exists()):
            self.error_message = "SLA artifacts are not present yet."
            return

        try:
            import joblib

            self._model = joblib.load(self.model_path)
            self._scaler = joblib.load(self.scaler_path)
            self._metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            self.available = True
        except Exception as exc:  # pragma: no cover
            self.error_message = str(exc)
            self.available = False

    def predict_sla_score(self, session: NetworkSession) -> float | None:
        if not self.available:
            return None

        import pandas as pd

        features = self._metadata.get("features", list(SLA_FEATURES))
        input_frame = pd.DataFrame([self._build_feature_row(session)])[features]
        scaled_values = self._scaler.transform(input_frame)
        probabilities = self._model.predict_proba(scaled_values)
        return float(probabilities[0][1])

    def recommend_action(self, session: NetworkSession, sla_score: float, fallback_action: str) -> str:
        if sla_score < 0.35 and session.public_safety:
            return "Prioriser immediatement les flux Public Safety et reserver de la capacite radio dediee."
        if sla_score < 0.45 and session.smart_city_home:
            return "Reduire la contention locale et lisser la charge sur les services Smart City and Home."
        if sla_score < 0.55 and session.iot_devices:
            return "Verifier les pics de trafic IoT et ajuster les politiques de scheduling de la slice."
        if sla_score < 0.55:
            return "Surveiller la derive SLA et declencher une optimisation radio avant saturation."
        return fallback_action

    def catalog_descriptor(self) -> ModelDescriptor:
        if self.available:
            return ModelDescriptor(
                name=self.name,
                purpose="Real SLA risk prediction from exported artifacts",
                implementation="HistGradientBoosting plus StandardScaler",
                status="ACTIVE",
                source_notebook="SLA_5G_Modeling.ipynb",
                artifact_path=self.artifact_root,
            )
        if self.error_message and self.model_path.exists():
            status = "ERROR"
            implementation = f"Artifact load failed: {self.error_message}"
        else:
            status = "MISSING_ARTIFACTS"
            implementation = "Awaiting exported model, scaler and metadata"
        return ModelDescriptor(
            name=self.name,
            purpose="Real SLA risk prediction from exported artifacts",
            implementation=implementation,
            status=status,
            source_notebook="SLA_5G_Modeling.ipynb",
            artifact_path=self.artifact_root,
        )

    def _build_feature_row(self, session: NetworkSession) -> dict[str, float]:
        return {
            "Packet Loss Rate": normalize_packet_loss(decimal_to_float(session.packet_loss)),
            "Packet delay": clamp(decimal_to_float(session.latency_ms), 0.0, 300.0),
            "Smart City & Home": float(session.smart_city_home),
            "IoT Devices": float(session.iot_devices),
            "Public Safety": float(session.public_safety),
        }


class RealCongestionBoostingProvider:
    name = "congestion-timeseries-adapter"
    version = "1.0.0"

    def __init__(self, *, model_path: str, metadata_path: str) -> None:
        self.model_path = Path(model_path)
        self.metadata_path = Path(metadata_path)
        self._model: Any = None
        self._metadata: dict[str, Any] = {}
        self.error_message: str | None = None
        self.available = False
        self._load_artifacts()

    @property
    def artifact_root(self) -> str:
        return self.model_path.parent.as_posix()

    def _load_artifacts(self) -> None:
        if not (self.model_path.exists() and self.metadata_path.exists()):
            self.error_message = "Congestion artifacts are not present yet."
            return

        try:
            import joblib

            self._model = joblib.load(self.model_path)
            self._metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            self.available = True
        except Exception as exc:  # pragma: no cover
            self.error_message = str(exc)
            self.available = False

    def predict_congestion_score(self, session: NetworkSession) -> float | None:
        if not self.available:
            return None

        import pandas as pd

        features = self._metadata.get("features", list(CONGESTION_FEATURES))
        input_frame = pd.DataFrame([self._build_feature_row(session)])[features]
        probabilities = self._model.predict_proba(input_frame)
        return float(probabilities[0][1])

    def recommend_action(self, session: NetworkSession, congestion_score: float, fallback_action: str) -> str:
        if congestion_score >= 0.82 and session.queue_len >= 10:
            return "Declencher un reequilibrage de charge immediat et alleger la region via steering inter-cellules."
        if congestion_score >= 0.70 and decimal_to_float(session.bw_util_pct) >= 85:
            return "Surveiller la saturation radio et preparer une extension de capacite sur les slices surchargees."
        return fallback_action

    def catalog_descriptor(self) -> ModelDescriptor:
        if self.available:
            return ModelDescriptor(
                name=self.name,
                purpose="Real congestion scoring from time-series telemetry",
                implementation="HistGradientBoosting on notebook-aligned features",
                status="ACTIVE",
                source_notebook="network_slicing_congestion_LSTM.ipynb",
                artifact_path=self.artifact_root,
            )
        if self.error_message and self.model_path.exists():
            status = "ERROR"
            implementation = f"Artifact load failed: {self.error_message}"
        else:
            status = "MISSING_ARTIFACTS"
            implementation = "Awaiting exported model and metadata"
        return ModelDescriptor(
            name=self.name,
            purpose="Real congestion scoring from time-series telemetry",
            implementation=implementation,
            status=status,
            source_notebook="network_slicing_congestion_LSTM.ipynb",
            artifact_path=self.artifact_root,
        )

    def _build_feature_row(self, session: NetworkSession) -> dict[str, float]:
        timestamp = session.timestamp
        hour = timestamp.hour if isinstance(timestamp, datetime) else 0
        return {
            "cpu_util_pct": clamp(decimal_to_float(session.cpu_util_pct), 0.0, 100.0),
            "mem_util_pct": clamp(decimal_to_float(session.mem_util_pct), 0.0, 100.0),
            "bw_util_pct": clamp(decimal_to_float(session.bw_util_pct), 0.0, 100.0),
            "active_users": float(session.active_users),
            "queue_len": float(session.queue_len),
            "hour": float(hour),
            "slice_type_encoded": float(self._resolve_slice_type_encoded(session.slice_type.value)),
        }

    def _resolve_slice_type_encoded(self, slice_type_value: str) -> int:
        mapping = self._metadata.get("slice_mapping", {})
        if slice_type_value in mapping:
            return int(mapping[slice_type_value])

        aliased_value = CONGESTION_SLICE_ALIASES.get(slice_type_value)
        if aliased_value and aliased_value in mapping:
            return int(mapping[aliased_value])

        fallback_key = next(iter(mapping.keys()), None)
        return int(mapping[fallback_key]) if fallback_key is not None else 0


class RealAnomalyIsolationForestProvider:
    name = "anomaly-misrouting-adapter"
    version = "1.0.0"

    def __init__(self, *, model_path: str, metadata_path: str) -> None:
        self.model_path = Path(model_path)
        self.metadata_path = Path(metadata_path)
        self._model: Any = None
        self._metadata: dict[str, Any] = {}
        self.error_message: str | None = None
        self.available = False
        self._load_artifacts()

    @property
    def artifact_root(self) -> str:
        return self.model_path.parent.as_posix()

    def _load_artifacts(self) -> None:
        if not (self.model_path.exists() and self.metadata_path.exists()):
            self.error_message = "Anomaly artifacts are not present yet."
            return

        try:
            import joblib

            self._model = joblib.load(self.model_path)
            self._metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            self.available = True
        except Exception as exc:  # pragma: no cover
            self.error_message = str(exc)
            self.available = False

    def evaluate(self, session: NetworkSession) -> AnomalyEvaluation | None:
        if not self.available:
            return None

        import pandas as pd

        feature_row = self._build_feature_row(session)
        features = self._metadata.get("features", list(ANOMALY_FEATURES))
        input_frame = pd.DataFrame([feature_row])[features]
        decision_score = float(self._model.decision_function(input_frame)[0])
        raw_model_score = -decision_score
        model_score = normalize_decision_score(
            raw_model_score,
            float(self._metadata.get("decision_score_min", -1.0)),
            float(self._metadata.get("decision_score_max", 1.0)),
        )

        misrouting_flag = bool(feature_row["slice_mismatch"])
        severity_score = clamp(float(feature_row["severity_score"]), 0.0, 1.0)
        anomaly_score = clamp((0.55 * model_score) + (0.25 * severity_score) + (0.20 * float(misrouting_flag)), 0.01, 0.99)

        return AnomalyEvaluation(
            anomaly_score=round(anomaly_score, 4),
            misrouting_flag=misrouting_flag,
            expected_slice_type=self._expected_slice_type(str(session.use_case_type)),
            violation_count=int(feature_row["violation_count"]),
            severity_score=round(severity_score, 4),
        )

    def recommend_action(self, evaluation: AnomalyEvaluation, fallback_action: str) -> str:
        if evaluation.misrouting_flag and evaluation.expected_slice_type:
            return (
                "Verifier un possible misrouting: le use case courant attend la slice "
                f"{evaluation.expected_slice_type}."
            )
        if evaluation.anomaly_score >= 0.82 and evaluation.violation_count >= 3:
            return "Inspecter immediatement les violations de budgets et verifier les politiques de transport et de steering."
        if evaluation.anomaly_score >= 0.65:
            return "Analyser les ecarts latence/jitter/packet loss et preparer une correction proactive de la slice."
        return fallback_action

    def catalog_descriptor(self) -> ModelDescriptor:
        if self.available:
            return ModelDescriptor(
                name=self.name,
                purpose="Real anomaly and misrouting detection from slice telemetry gaps",
                implementation="IsolationForest plus runtime misrouting rules",
                status="ACTIVE",
                source_notebook="slice_misrouting_anomaly_pipeline.ipynb",
                artifact_path=self.artifact_root,
            )
        if self.error_message and self.model_path.exists():
            status = "ERROR"
            implementation = f"Artifact load failed: {self.error_message}"
        else:
            status = "MISSING_ARTIFACTS"
            implementation = "Awaiting exported model and metadata"
        return ModelDescriptor(
            name=self.name,
            purpose="Real anomaly and misrouting detection from slice telemetry gaps",
            implementation=implementation,
            status=status,
            source_notebook="slice_misrouting_anomaly_pipeline.ipynb",
            artifact_path=self.artifact_root,
        )

    def _build_feature_row(self, session: NetworkSession) -> dict[str, float]:
        packet_loss_budget = max(decimal_to_float(session.packet_loss_budget), 1e-6)
        latency_budget_ns = max(float(session.latency_budget_ns), 1.0)
        jitter_budget_ns = max(float(session.jitter_budget_ns), 1.0)
        available_transfer = max(decimal_to_float(session.slice_available_transfer_rate_gbps), 1.0)
        slice_packet_loss = decimal_to_float(session.slice_packet_loss)
        slice_latency_ns = float(session.slice_latency_ns)
        slice_jitter_ns = float(session.slice_jitter_ns)
        data_rate_budget = decimal_to_float(session.data_rate_budget_gbps)

        latency_gap_ns = max(slice_latency_ns - latency_budget_ns, 0.0)
        jitter_gap_ns = max(slice_jitter_ns - jitter_budget_ns, 0.0)
        packet_loss_gap = max(slice_packet_loss - packet_loss_budget, 0.0)
        data_rate_gap_gbps = max(data_rate_budget - available_transfer, 0.0)

        latency_ratio = slice_latency_ns / latency_budget_ns
        jitter_ratio = slice_jitter_ns / jitter_budget_ns
        packet_loss_ratio = slice_packet_loss / packet_loss_budget
        data_rate_ratio = data_rate_budget / available_transfer
        expected_slice_type = self._expected_slice_type(str(session.use_case_type))
        current_slice = self._normalize_slice_for_anomaly(session.slice_type.value)
        misrouting_flag = int(bool(expected_slice_type) and current_slice != expected_slice_type)

        violation_count = (
            int(latency_gap_ns > 0)
            + int(jitter_gap_ns > 0)
            + int(packet_loss_gap > 0)
            + int(data_rate_gap_gbps > 0)
            + misrouting_flag
        )
        weighted_violation_score = (
            (latency_ratio * 0.28)
            + (jitter_ratio * 0.17)
            + (packet_loss_ratio * 0.22)
            + (data_rate_ratio * 0.18)
            + (float(session.required_mobility) * 0.05)
            + (float(session.required_connectivity) * 0.05)
            + (float(session.slice_handover) * 0.05)
            + (misrouting_flag * 0.25)
        )
        severity_score = clamp((weighted_violation_score / 4.0) * 0.7 + (violation_count / 5.0) * 0.3, 0.0, 1.0)

        return {
            "latency_gap_ns": latency_gap_ns,
            "jitter_gap_ns": jitter_gap_ns,
            "packet_loss_gap": packet_loss_gap,
            "data_rate_gap_gbps": data_rate_gap_gbps,
            "latency_ratio": latency_ratio,
            "jitter_ratio": jitter_ratio,
            "packet_loss_ratio": packet_loss_ratio,
            "data_rate_ratio": data_rate_ratio,
            "violation_count": float(violation_count),
            "weighted_violation_score": weighted_violation_score,
            "severity_score": severity_score,
            "required_mobility_flag": float(bool(session.required_mobility)),
            "required_connectivity_flag": float(bool(session.required_connectivity)),
            "slice_handover_flag": float(bool(session.slice_handover)),
            "slice_mismatch": float(misrouting_flag),
        }

    def _expected_slice_type(self, use_case_type: str) -> str | None:
        expected_map = self._metadata.get("expected_slice_map", {})
        value = expected_map.get(use_case_type)
        return str(value) if value else None

    def _normalize_slice_for_anomaly(self, slice_type_value: str) -> str:
        return ANOMALY_SLICE_ALIASES.get(slice_type_value, slice_type_value)


class RealSliceLightGBMProvider:
    name = "slice-lightgbm-adapter"
    version = "1.0.0"

    def __init__(self, *, model_path: str, metadata_path: str) -> None:
        self.model_path = Path(model_path)
        self.metadata_path = Path(metadata_path)
        self._model: dict[str, Any] = {}
        self._runtime: LightGBMBoosterRuntime | None = None
        self._metadata: dict[str, Any] = {}
        self.error_message: str | None = None
        self.available = False
        self._load_artifacts()

    @property
    def artifact_root(self) -> str:
        return self.model_path.parent.as_posix()

    def _load_artifacts(self) -> None:
        if not (self.model_path.exists() and self.metadata_path.exists()):
            self.error_message = "Slice classification artifacts are not present yet."
            return

        try:
            self._model = json.loads(self.model_path.read_text(encoding="utf-8"))
            self._metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            self._runtime = LightGBMBoosterRuntime(self._model)
            self.available = True
        except Exception as exc:  # pragma: no cover
            self.error_message = str(exc)
            self.available = False

    def predict_slice(self, session: NetworkSession) -> tuple[Any, float] | None:
        if not self.available or self._runtime is None:
            return None

        features = self._metadata.get("features", list(SLICE_FEATURES))
        classes = self._metadata.get("classes", ["eMBB", "mMTC", "URLLC"])
        feature_row = self._build_feature_row(session)
        runtime_row = {feature_name: feature_row[feature_name] for feature_name in features}
        probabilities = self._runtime.predict_proba(runtime_row)
        best_index = int(max(range(len(probabilities)), key=lambda index: probabilities[index]))
        predicted_class = str(classes[best_index])
        predicted_slice_type = SLICE_CLASS_TO_RUNTIME.get(predicted_class, session.slice_type)
        confidence = float(probabilities[best_index])
        return predicted_slice_type, round(confidence, 4)

    def recommend_action(
        self,
        session: NetworkSession,
        predicted_slice_type: Any,
        confidence: float,
        fallback_action: str,
    ) -> str:
        expected_group = normalize_slice_class(predicted_slice_type)
        current_group = normalize_slice_class(session.slice_type)

        if confidence >= 0.75 and expected_group != current_group:
            return (
                "Verifier la classification de slice: le moteur LightGBM suggere "
                f"{predicted_slice_type.value} avec une confiance de {confidence:.0%}."
            )
        if confidence < 0.45:
            return "Classification slice a faible confiance, conserver la supervision operateur et confirmer le contexte service."
        return fallback_action

    def catalog_descriptor(self) -> ModelDescriptor:
        if self.available:
            return ModelDescriptor(
                name=self.name,
                purpose="Real slice classification from notebook-exported LightGBM artifacts",
                implementation="LightGBM booster dump plus pure Python runtime",
                status="ACTIVE",
                source_notebook="LightGBM_Only.ipynb",
                artifact_path=self.artifact_root,
            )
        if self.error_message and self.model_path.exists():
            status = "ERROR"
            implementation = f"Artifact load failed: {self.error_message}"
        else:
            status = "MISSING_ARTIFACTS"
            implementation = "Awaiting exported LightGBM model and metadata"
        return ModelDescriptor(
            name=self.name,
            purpose="Real slice classification from notebook-exported LightGBM artifacts",
            implementation=implementation,
            status=status,
            source_notebook="LightGBM_Only.ipynb",
            artifact_path=self.artifact_root,
        )

    def _build_feature_row(self, session: NetworkSession) -> dict[str, float]:
        packet_delay_divisor = float(self._metadata.get("runtime_packet_delay_divisor", 1.0))
        return {
            "LTE/5g Category": float(session.lte_5g_category),
            "Packet Loss Rate": normalize_packet_loss(decimal_to_float(session.packet_loss)),
            "Packet delay": normalize_packet_delay(decimal_to_float(session.latency_ms), divisor=packet_delay_divisor),
            "Smartphone": float(session.smartphone),
            "IoT Devices": float(session.iot_devices),
            "GBR": float(session.gbr),
        }
