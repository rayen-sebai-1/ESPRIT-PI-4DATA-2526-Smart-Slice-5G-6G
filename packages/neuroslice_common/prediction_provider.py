from __future__ import annotations

from packages.neuroslice_common.config import Settings
from packages.neuroslice_common.models import NetworkSession, Region
from packages.neuroslice_common.prediction_common import (
    ModelDescriptor,
    PredictionProvider,
    PredictionResult,
    compute_risk_level,
)
from packages.neuroslice_common.prediction_mock import MockPredictionProvider
from packages.neuroslice_common.prediction_real import (
    RealAnomalyIsolationForestProvider,
    RealCongestionBoostingProvider,
    RealSLABoostingProvider,
    RealSliceLightGBMProvider,
)


class HybridPredictionProvider:
    name = "hybrid-real-plus-fallback"
    version = "1.3.0"

    def __init__(
        self,
        *,
        mock_provider: MockPredictionProvider,
        sla_provider: RealSLABoostingProvider | None,
        congestion_provider: RealCongestionBoostingProvider | None,
        anomaly_provider: RealAnomalyIsolationForestProvider | None,
        slice_provider: RealSliceLightGBMProvider | None,
    ) -> None:
        self.mock_provider = mock_provider
        self.sla_provider = sla_provider
        self.congestion_provider = congestion_provider
        self.anomaly_provider = anomaly_provider
        self.slice_provider = slice_provider

    def predict(self, session: NetworkSession, region: Region) -> PredictionResult:
        baseline = self.mock_provider.predict(session, region)

        sla_score = baseline.sla_score
        congestion_score = baseline.congestion_score
        anomaly_score = baseline.anomaly_score
        predicted_slice_type = baseline.predicted_slice_type
        slice_confidence = baseline.slice_confidence
        recommended_action = baseline.recommended_action
        model_sources = [f"{self.mock_provider.name}:{self.mock_provider.version}"]

        if self.sla_provider is not None and self.sla_provider.available:
            real_sla_score = self.sla_provider.predict_sla_score(session)
            if real_sla_score is not None:
                sla_score = round(real_sla_score, 4)
                recommended_action = self.sla_provider.recommend_action(session, sla_score, recommended_action)
                model_sources.insert(0, f"{self.sla_provider.name}:{self.sla_provider.version}")

        if self.congestion_provider is not None and self.congestion_provider.available:
            real_congestion_score = self.congestion_provider.predict_congestion_score(session)
            if real_congestion_score is not None:
                congestion_score = round(real_congestion_score, 4)
                recommended_action = self.congestion_provider.recommend_action(session, congestion_score, recommended_action)
                model_sources.insert(0, f"{self.congestion_provider.name}:{self.congestion_provider.version}")

        if self.anomaly_provider is not None and self.anomaly_provider.available:
            evaluation = self.anomaly_provider.evaluate(session)
            if evaluation is not None:
                anomaly_score = evaluation.anomaly_score
                recommended_action = self.anomaly_provider.recommend_action(evaluation, recommended_action)
                model_sources.insert(0, f"{self.anomaly_provider.name}:{self.anomaly_provider.version}")

        if self.slice_provider is not None and self.slice_provider.available:
            slice_prediction = self.slice_provider.predict_slice(session)
            if slice_prediction is not None:
                predicted_slice_type, slice_confidence = slice_prediction
                recommended_action = self.slice_provider.recommend_action(
                    session,
                    predicted_slice_type,
                    slice_confidence,
                    recommended_action,
                )
                model_sources.insert(0, f"{self.slice_provider.name}:{self.slice_provider.version}")

        risk_level = compute_risk_level(sla_score, congestion_score, anomaly_score)
        return PredictionResult(
            sla_score=sla_score,
            congestion_score=congestion_score,
            anomaly_score=anomaly_score,
            risk_level=risk_level,
            predicted_slice_type=predicted_slice_type,
            slice_confidence=slice_confidence,
            recommended_action=recommended_action,
            model_source="|".join(model_sources),
        )

    def catalog(self) -> list[ModelDescriptor]:
        sla_descriptor = (
            self.sla_provider.catalog_descriptor()
            if self.sla_provider is not None
            else ModelDescriptor(
                name="sla-boosting-adapter",
                purpose="Real SLA risk prediction from exported artifacts",
                implementation="Awaiting provider configuration",
                status="PLANNED",
                source_notebook="SLA_5G_Modeling.ipynb",
                artifact_path="data/models/sla/",
            )
        )
        congestion_descriptor = (
            self.congestion_provider.catalog_descriptor()
            if self.congestion_provider is not None
            else ModelDescriptor(
                name="congestion-timeseries-adapter",
                purpose="Real congestion scoring from time-series telemetry",
                implementation="Awaiting provider configuration",
                status="PLANNED",
                source_notebook="network_slicing_congestion_LSTM.ipynb",
                artifact_path="data/models/congestion/",
            )
        )
        anomaly_descriptor = (
            self.anomaly_provider.catalog_descriptor()
            if self.anomaly_provider is not None
            else ModelDescriptor(
                name="anomaly-misrouting-adapter",
                purpose="Real anomaly and misrouting detection",
                implementation="Awaiting provider configuration",
                status="PLANNED",
                source_notebook="slice_misrouting_anomaly_pipeline.ipynb",
                artifact_path="data/models/anomaly/",
            )
        )
        slice_descriptor = (
            self.slice_provider.catalog_descriptor()
            if self.slice_provider is not None
            else ModelDescriptor(
                name="slice-lightgbm-adapter",
                purpose="Real slice classification from notebook-exported LightGBM artifacts",
                implementation="Awaiting provider configuration",
                status="PLANNED",
                source_notebook="LightGBM_Only.ipynb",
                artifact_path="data/models/slice/",
            )
        )

        include_mock_as_active = not any(
            (
                self.sla_provider and self.sla_provider.available,
                self.congestion_provider and self.congestion_provider.available,
                self.anomaly_provider and self.anomaly_provider.available,
                self.slice_provider and self.slice_provider.available,
            )
        )
        return build_model_catalog(
            sla_descriptor=sla_descriptor,
            congestion_descriptor=congestion_descriptor,
            anomaly_descriptor=anomaly_descriptor,
            slice_descriptor=slice_descriptor,
            include_mock_as_active=include_mock_as_active,
        )


def build_model_catalog(
    *,
    sla_descriptor: ModelDescriptor,
    congestion_descriptor: ModelDescriptor,
    anomaly_descriptor: ModelDescriptor,
    slice_descriptor: ModelDescriptor,
    include_mock_as_active: bool,
) -> list[ModelDescriptor]:
    mock_status = "ACTIVE" if include_mock_as_active else "FALLBACK"
    return [
        ModelDescriptor(
            name="mock-telecom-heuristic",
            purpose="Fallback scoring for unavailable models and slice classification",
            implementation="Deterministic heuristics",
            status=mock_status,
            source_notebook="N/A - deterministic rules for MVP",
            artifact_path=None,
        ),
        sla_descriptor,
        congestion_descriptor,
        anomaly_descriptor,
        slice_descriptor,
    ]


def get_prediction_provider(settings: Settings) -> PredictionProvider:
    provider_name = settings.prediction_provider.strip().lower()
    mock_provider = MockPredictionProvider()
    real_sla_provider = RealSLABoostingProvider(
        model_path=settings.sla_model_path,
        scaler_path=settings.sla_scaler_path,
        metadata_path=settings.sla_metadata_path,
    )
    real_congestion_provider = RealCongestionBoostingProvider(
        model_path=settings.congestion_model_path,
        metadata_path=settings.congestion_metadata_path,
    )
    real_anomaly_provider = RealAnomalyIsolationForestProvider(
        model_path=settings.anomaly_model_path,
        metadata_path=settings.anomaly_metadata_path,
    )
    real_slice_provider = RealSliceLightGBMProvider(
        model_path=settings.slice_model_path,
        metadata_path=settings.slice_metadata_path,
    )

    if provider_name == "mock":
        return mock_provider
    if provider_name == "sla-real":
        return HybridPredictionProvider(
            mock_provider=mock_provider,
            sla_provider=real_sla_provider,
            congestion_provider=None,
            anomaly_provider=None,
            slice_provider=None,
        )
    return HybridPredictionProvider(
        mock_provider=mock_provider,
        sla_provider=real_sla_provider,
        congestion_provider=real_congestion_provider,
        anomaly_provider=real_anomaly_provider,
        slice_provider=real_slice_provider,
    )
