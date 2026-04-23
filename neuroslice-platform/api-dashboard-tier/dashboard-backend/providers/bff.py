from __future__ import annotations

from datetime import UTC, datetime

import httpx
from fastapi import HTTPException, status

from providers.base import DashboardDataProvider
from schemas import (
    ModelInfo,
    NationalDashboardResponse,
    NationalOverview,
    RegionDashboardResponse,
    RunBatchRequest,
    SessionListResponse,
    SessionSummary,
)


class BffDashboardProvider(DashboardDataProvider):
    name = "bff"

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=10.0)

    def _get_json(self, path: str, **params: object) -> dict:
        response = self.client.get(path, params=params)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Unexpected payload returned by BFF for {path}.",
            )
        return payload

    @staticmethod
    def _average(items: list[float]) -> float:
        return round(sum(items) / len(items), 2) if items else 0.0

    def get_national_dashboard(self) -> NationalDashboardResponse:
        latest_kpis = self._get_json("/api/v1/kpis/latest", limit=500).get("entities", [])
        congestion_items = self._get_json("/api/v1/aiops/congestion/latest", limit=500).get("items", [])
        sla_items = self._get_json("/api/v1/aiops/sla/latest", limit=500).get("items", [])
        anomaly_events = self._get_json("/api/v1/aiops/events/recent", stream="events.anomaly", count=200).get("events", [])

        latencies = []
        for entity in latest_kpis if isinstance(latest_kpis, list) else []:
            kpis = entity.get("kpis", {}) if isinstance(entity, dict) else {}
            if isinstance(kpis, dict):
                raw_latency = kpis.get("latencyMs") or kpis.get("latency_ms")
                if isinstance(raw_latency, (float, int)):
                    latencies.append(float(raw_latency))

        congestion_scores = []
        for item in congestion_items if isinstance(congestion_items, list) else []:
            if isinstance(item, dict):
                value = item.get("congestionScore") or item.get("score") or item.get("value")
                if isinstance(value, (float, int)):
                    congestion_scores.append(float(value) * 100 if float(value) <= 1 else float(value))

        sla_scores = []
        for item in sla_items if isinstance(sla_items, list) else []:
            if isinstance(item, dict):
                value = item.get("slaScore") or item.get("score") or item.get("value")
                if isinstance(value, (float, int)):
                    normalized = float(value)
                    sla_scores.append((1 - normalized) * 100 if normalized <= 1 else normalized)

        overview = NationalOverview(
            sla_national_percent=self._average(sla_scores),
            avg_latency_ms=self._average(latencies),
            congestion_rate=self._average(congestion_scores),
            active_alerts_count=len([score for score in congestion_scores if score >= 70]),
            sessions_count=len(latest_kpis) if isinstance(latest_kpis, list) else 0,
            anomalies_count=len(anomaly_events) if isinstance(anomaly_events, list) else 0,
            generated_at=datetime.now(UTC),
        )
        return NationalDashboardResponse(overview=overview, regions=[])

    def _not_supported(self, capability: str):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"BffDashboardProvider cannot serve {capability} with the current api-bff-service surface.",
        )

    def get_region_dashboard(self, region_id: int) -> RegionDashboardResponse | None:
        self._not_supported("regional dashboard views")

    def list_sessions(
        self,
        *,
        region: str | None,
        risk: str | None,
        slice_type: str | None,
        page: int,
        page_size: int,
    ) -> SessionListResponse:
        self._not_supported("session aggregation")

    def get_session(self, session_id: int) -> SessionSummary | None:
        self._not_supported("session detail lookups")

    def list_predictions(
        self,
        *,
        region: str | None,
        risk: str | None,
        page: int,
        page_size: int,
    ):
        self._not_supported("prediction lists")

    def get_prediction(self, session_id: int):
        self._not_supported("prediction detail lookups")

    def run_prediction(self, session_id: int):
        self._not_supported("prediction execution")

    def run_batch(self, payload: RunBatchRequest):
        self._not_supported("batch prediction execution")

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                name="bff-live-provider",
                purpose="Future live dashboard adapter backed by api-bff-service",
                implementation="HTTP aggregation over /api/v1/kpis and /api/v1/aiops",
                status="READY_FOR_EXTENSION",
                source_notebook="N/A - operational data provider",
                artifact_path=None,
            )
        ]
