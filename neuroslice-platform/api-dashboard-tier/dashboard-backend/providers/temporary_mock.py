from __future__ import annotations

import math
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime, timedelta

from providers.base import DashboardDataProvider
from schemas import (
    ModelInfo,
    NationalDashboardResponse,
    NationalOverview,
    PaginationMeta,
    PredictionResponse,
    PredictionSummary,
    RegionComparison,
    RegionDashboardResponse,
    RegionLite,
    RegionSummary,
    RunBatchRequest,
    SessionListResponse,
    SessionSummary,
    SliceDistributionPoint,
    TrendPoint,
)

NOW = datetime(2026, 4, 18, 21, 0, tzinfo=UTC)
REGIONS = [
    {"region_id": 1, "code": "GT", "name": "Grand Tunis", "ric_status": "DEGRADED", "network_load": 88.0, "gnodeb_count": 96, "sessions_count": 24, "sla_percent": 63.0, "avg_latency_ms": 21.4, "avg_packet_loss": 1.28, "congestion_rate": 71.0, "high_risk_sessions_count": 8, "anomalies_count": 4},
    {"region_id": 2, "code": "CB", "name": "Cap Bon", "ric_status": "HEALTHY", "network_load": 73.0, "gnodeb_count": 52, "sessions_count": 14, "sla_percent": 74.0, "avg_latency_ms": 18.2, "avg_packet_loss": 0.91, "congestion_rate": 53.0, "high_risk_sessions_count": 3, "anomalies_count": 1},
    {"region_id": 3, "code": "SH", "name": "Sahel", "ric_status": "DEGRADED", "network_load": 68.0, "gnodeb_count": 71, "sessions_count": 16, "sla_percent": 70.0, "avg_latency_ms": 17.5, "avg_packet_loss": 0.78, "congestion_rate": 48.0, "high_risk_sessions_count": 4, "anomalies_count": 2},
    {"region_id": 4, "code": "SF", "name": "Sfax", "ric_status": "DEGRADED", "network_load": 70.0, "gnodeb_count": 66, "sessions_count": 18, "sla_percent": 68.0, "avg_latency_ms": 19.1, "avg_packet_loss": 0.95, "congestion_rate": 55.0, "high_risk_sessions_count": 5, "anomalies_count": 2},
    {"region_id": 5, "code": "NO", "name": "Nord Ouest", "ric_status": "HEALTHY", "network_load": 49.0, "gnodeb_count": 31, "sessions_count": 10, "sla_percent": 79.0, "avg_latency_ms": 15.6, "avg_packet_loss": 0.42, "congestion_rate": 31.0, "high_risk_sessions_count": 1, "anomalies_count": 0},
    {"region_id": 6, "code": "CO", "name": "Centre Ouest", "ric_status": "HEALTHY", "network_load": 54.0, "gnodeb_count": 38, "sessions_count": 12, "sla_percent": 76.0, "avg_latency_ms": 16.2, "avg_packet_loss": 0.58, "congestion_rate": 35.0, "high_risk_sessions_count": 2, "anomalies_count": 1},
    {"region_id": 7, "code": "SE", "name": "Sud Est", "ric_status": "HEALTHY", "network_load": 46.0, "gnodeb_count": 29, "sessions_count": 10, "sla_percent": 81.0, "avg_latency_ms": 14.8, "avg_packet_loss": 0.33, "congestion_rate": 29.0, "high_risk_sessions_count": 1, "anomalies_count": 0},
    {"region_id": 8, "code": "SO", "name": "Sud Ouest", "ric_status": "HEALTHY", "network_load": 33.0, "gnodeb_count": 22, "sessions_count": 8, "sla_percent": 85.0, "avg_latency_ms": 13.4, "avg_packet_loss": 0.21, "congestion_rate": 19.0, "high_risk_sessions_count": 0, "anomalies_count": 0},
]


def _region_summary(region: dict) -> RegionSummary:
    return RegionSummary(
        id=region["region_id"],
        code=region["code"],
        name=region["name"],
        ric_status=region["ric_status"],
        network_load=region["network_load"],
        gnodeb_count=region["gnodeb_count"],
    )


def _region_lite(region: dict) -> RegionLite:
    return RegionLite(
        id=region["region_id"],
        code=region["code"],
        name=region["name"],
        ric_status=region["ric_status"],
        network_load=region["network_load"],
    )


def _paginate(items: list[object], page: int, page_size: int) -> PaginationMeta:
    total = len(items)
    total_pages = max(1, math.ceil(total / page_size))
    return PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages)


def _build_dataset() -> tuple[list[dict], list[dict]]:
    sessions: list[dict] = []
    predictions: list[dict] = []
    prediction_id = 1
    session_id = 1
    slice_cycle = ["eMBB", "URLLC", "mMTC", "ERLLC", "feMBB", "MBRLLC"]

    for region in REGIONS:
        for index in range(min(region["sessions_count"], 8)):
            slice_type = slice_cycle[(session_id - 1) % len(slice_cycle)]
            latency = round(region["avg_latency_ms"] + (index % 4) * 1.4, 1)
            packet_loss = round(region["avg_packet_loss"] + ((index % 3) * 0.17), 2)
            throughput = round(120 - region["network_load"] * 0.7 - index * 2.3, 1)
            risk = "LOW"
            if region["network_load"] > 80 or index >= 6:
                risk = "HIGH"
            if packet_loss > 1.3 or latency > 24:
                risk = "CRITICAL"
            elif packet_loss > 0.85 or latency > 19:
                risk = "MEDIUM" if risk == "LOW" else risk

            prediction = {
                "id": prediction_id,
                "session_id": session_id,
                "session_code": f"NS-{region['code']}-{index + 1:03d}",
                "region": _region_lite(region),
                "sla_score": round(max(0.1, 1 - region["sla_percent"] / 100 + index * 0.03), 2),
                "congestion_score": round(min(0.98, region["congestion_rate"] / 100 + index * 0.025), 2),
                "anomaly_score": round(min(0.95, region["anomalies_count"] * 0.12 + index * 0.05), 2),
                "risk_level": risk,
                "predicted_slice_type": slice_type,
                "slice_confidence": round(0.82 + (index % 4) * 0.04, 2),
                "recommended_action": (
                    "Reequilibrer la charge et surveiller la region."
                    if risk in {"HIGH", "CRITICAL"}
                    else "Maintenir une surveillance standard."
                ),
                "model_source": "draft-scorer-v1",
                "predicted_at": NOW - timedelta(minutes=prediction_id * 7),
            }
            session = {
                "id": session_id,
                "session_code": prediction["session_code"],
                "region": _region_summary(region),
                "slice_type": slice_type,
                "latency_ms": latency,
                "packet_loss": packet_loss,
                "throughput_mbps": throughput,
                "timestamp": NOW - timedelta(minutes=session_id * 9),
                "prediction": PredictionSummary(**prediction),
            }
            sessions.append(session)
            predictions.append(prediction)
            prediction_id += 1
            session_id += 1

    return sessions, predictions


class TemporaryMockProvider(DashboardDataProvider):
    name = "temporary_mock"

    def __init__(self) -> None:
        self.sessions, self.predictions = _build_dataset()

    def get_national_dashboard(self) -> NationalDashboardResponse:
        total_sessions = sum(region["sessions_count"] for region in REGIONS)
        overview = NationalOverview(
            sla_national_percent=round(sum(region["sla_percent"] * region["sessions_count"] for region in REGIONS) / total_sessions, 2),
            avg_latency_ms=round(sum(region["avg_latency_ms"] * region["sessions_count"] for region in REGIONS) / total_sessions, 2),
            congestion_rate=round(sum(region["congestion_rate"] * region["sessions_count"] for region in REGIONS) / total_sessions, 2),
            active_alerts_count=sum(region["high_risk_sessions_count"] for region in REGIONS),
            sessions_count=total_sessions,
            anomalies_count=sum(region["anomalies_count"] for region in REGIONS),
            generated_at=NOW,
        )
        return NationalDashboardResponse(
            overview=overview,
            regions=[RegionComparison(**region) for region in REGIONS],
        )

    def get_region_dashboard(self, region_id: int) -> RegionDashboardResponse | None:
        region = next((item for item in REGIONS if item["region_id"] == region_id), None)
        if region is None:
            return None

        sessions = [item for item in self.sessions if item["region"].id == region_id]
        distribution = Counter(session["slice_type"] for session in sessions)
        trend: list[TrendPoint] = []
        for offset in range(6, -1, -1):
            day = NOW - timedelta(days=offset)
            trend.append(
                TrendPoint(
                    label=day.strftime("%Y-%m-%d"),
                    generated_at=day,
                    sla_percent=max(45.0, round(region["sla_percent"] - offset * 0.8, 2)),
                    congestion_rate=min(95.0, round(region["congestion_rate"] + (6 - offset) * 1.2, 2)),
                    active_alerts_count=max(0, region["high_risk_sessions_count"] - offset // 2),
                    anomalies_count=region["anomalies_count"],
                    total_sessions=region["sessions_count"],
                )
            )

        return RegionDashboardResponse(
            region=RegionComparison(**region),
            gnodeb_count=region["gnodeb_count"],
            packet_loss_avg=region["avg_packet_loss"],
            slice_distribution=[SliceDistributionPoint(slice_type=key, sessions_count=value) for key, value in distribution.items()],
            trend=trend,
        )

    def list_sessions(
        self,
        *,
        region: str | None,
        risk: str | None,
        slice_type: str | None,
        page: int,
        page_size: int,
    ) -> SessionListResponse:
        items = deepcopy(self.sessions)
        if region:
            term = region.lower()
            items = [item for item in items if term in item["region"].name.lower() or term in item["region"].code.lower()]
        if risk:
            items = [item for item in items if item["prediction"] and item["prediction"].risk_level == risk]
        if slice_type:
            items = [item for item in items if item["slice_type"] == slice_type]
        items.sort(key=lambda item: item["timestamp"], reverse=True)
        meta = _paginate(items, page, page_size)
        start = (page - 1) * page_size
        end = start + page_size
        return SessionListResponse(items=[SessionSummary(**item) for item in items[start:end]], pagination=meta)

    def get_session(self, session_id: int) -> SessionSummary | None:
        for session in self.sessions:
            if session["id"] == session_id:
                return SessionSummary(**deepcopy(session))
        return None

    def list_predictions(
        self,
        *,
        region: str | None,
        risk: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[PredictionResponse], PaginationMeta]:
        items = deepcopy(self.predictions)
        if region:
            term = region.lower()
            items = [item for item in items if term in item["region"].name.lower() or term in item["region"].code.lower()]
        if risk:
            items = [item for item in items if item["risk_level"] == risk]
        items.sort(key=lambda item: item["predicted_at"], reverse=True)
        meta = _paginate(items, page, page_size)
        start = (page - 1) * page_size
        end = start + page_size
        return [PredictionResponse(**item) for item in items[start:end]], meta

    def get_prediction(self, session_id: int) -> PredictionResponse | None:
        for prediction in self.predictions:
            if prediction["session_id"] == session_id:
                return PredictionResponse(**deepcopy(prediction))
        return None

    def run_prediction(self, session_id: int) -> PredictionResponse | None:
        for prediction in self.predictions:
            if prediction["session_id"] == session_id:
                prediction["predicted_at"] = datetime.now(UTC)
                prediction["congestion_score"] = round(min(0.99, prediction["congestion_score"] + 0.01), 2)
                prediction["sla_score"] = round(min(0.99, prediction["sla_score"] + 0.01), 2)
                if prediction["congestion_score"] >= 0.7 or prediction["sla_score"] >= 0.55:
                    prediction["risk_level"] = "HIGH" if prediction["risk_level"] != "CRITICAL" else "CRITICAL"
                for session in self.sessions:
                    if session["id"] == session_id:
                        session["prediction"] = PredictionSummary(**prediction)
                        break
                return PredictionResponse(**deepcopy(prediction))
        return None

    def run_batch(self, payload: RunBatchRequest) -> list[PredictionResponse]:
        target_sessions = self.sessions
        if payload.region_id is not None:
            target_sessions = [session for session in self.sessions if session["region"].id == payload.region_id]
        results: list[PredictionResponse] = []
        for session in target_sessions[: payload.limit]:
            prediction = self.run_prediction(session["id"])
            if prediction is not None:
                results.append(prediction)
        return results

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                name="draft-auth-aware-scorer",
                purpose="Scoring demo pour le dashboard de transition",
                implementation="TemporaryMockProvider deterministic rules",
                status="TRANSITIONAL",
                source_notebook="Aucun - fournisseur temporaire pour Scenario B",
                artifact_path=None,
            ),
            ModelInfo(
                name="regional-risk-prioritizer",
                purpose="Priorisation simple des regions et sessions a surveiller",
                implementation="Rules + weighted regional KPIs",
                status="TRANSITIONAL",
                source_notebook="Aucun - logique de demonstration isolee",
                artifact_path=None,
            ),
        ]
