from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import HTTPException, status

from providers.base import DashboardDataProvider
from schemas import (
    ModelInfo,
    NationalDashboardResponse,
    NationalOverview,
    PaginationMeta,
    PredictionListResponse,
    PredictionResponse,
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

_VALID_SLICE_TYPES = frozenset(
    {"eMBB", "URLLC", "mMTC", "ERLLC", "feMBB", "umMTC", "MBRLLC", "mURLLC"}
)
_DEFAULT_SLICE_TYPE = "eMBB"

_REGION_INT_TO_DOMAIN: dict[int, str] = {1: "core", 2: "edge", 3: "ran"}
_DOMAIN_TO_REGION_INT: dict[str, int] = {"core": 1, "edge": 2, "ran": 3}
_DOMAIN_META: dict[str, dict[str, str]] = {
    "core": {"code": "CORE", "name": "Core network"},
    "edge": {"code": "EDGE", "name": "Edge & MEC"},
    "ran": {"code": "RAN", "name": "Radio access (RAN)"},
}


def _entity_int_id(entity_id: str) -> int:
    return abs(hash(entity_id)) % (2**31 - 2) + 1


def _health_to_ric_status(health: float) -> str:
    if health >= 0.8:
        return "HEALTHY"
    if health >= 0.6:
        return "DEGRADED"
    return "CRITICAL"


def _risk_from_scores(congestion: float, sla: float) -> str:
    score = max(congestion, sla)
    if score >= 0.8:
        return "CRITICAL"
    if score >= 0.6:
        return "HIGH"
    if score >= 0.4:
        return "MEDIUM"
    return "LOW"


def _recommended_action(risk_level: str) -> str:
    return {
        "CRITICAL": "Immediate intervention required: isolate affected slices and scale resources.",
        "HIGH": "Investigate congestion and SLA metrics; consider slice reallocation.",
        "MEDIUM": "Monitor closely; pre-emptively review RAN load distribution.",
        "LOW": "No action required; continue standard monitoring.",
    }.get(risk_level, "Review network metrics.")


def _normalize_score(value: Any) -> float:
    if value is None:
        return 0.0
    v = float(value)
    return v / 100.0 if v > 1.0 else v


def _parse_ts(ts_str: Any, fallback: datetime) -> datetime:
    if not ts_str:
        return fallback
    try:
        s = str(ts_str).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return fallback


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
        try:
            faults_payload = self._get_json("/api/v1/live/faults")
            active_faults = faults_payload.get("faults", []) or []
            active_faults_count = len(active_faults) if isinstance(active_faults, list) else 0
        except Exception:
            active_faults_count = 0

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
                    congestion_scores.append(_normalize_score(value) * 100)

        sla_scores = []
        for item in sla_items if isinstance(sla_items, list) else []:
            if isinstance(item, dict):
                value = item.get("slaScore") or item.get("score") or item.get("value")
                if isinstance(value, (float, int)):
                    normalized = _normalize_score(value)
                    sla_scores.append((1 - normalized) * 100)

        overview = NationalOverview(
            sla_national_percent=self._average(sla_scores),
            avg_latency_ms=self._average(latencies),
            congestion_rate=self._average(congestion_scores),
            active_alerts_count=len([s for s in congestion_scores if s >= 70]) + active_faults_count,
            sessions_count=len(latest_kpis) if isinstance(latest_kpis, list) else 0,
            anomalies_count=len(anomaly_events) if isinstance(anomaly_events, list) else 0,
            generated_at=datetime.now(UTC),
        )
        return NationalDashboardResponse(overview=overview, regions=[])

    # ---- Regional dashboard ----

    def get_region_dashboard(self, region_id: int) -> RegionDashboardResponse | None:
        domain = _REGION_INT_TO_DOMAIN.get(region_id)
        if domain is None:
            return None

        try:
            data = self._get_json(f"/api/v1/network/region/{domain}")
        except HTTPException as exc:
            if exc.status_code == 404:
                return None
            raise

        now = datetime.now(UTC)
        kpis: dict = data.get("kpis") or {}
        health_avg = float(kpis.get("health_avg") or 0.8)
        congestion_avg = float(kpis.get("congestion_avg") or 0.0)
        latency_avg = float(kpis.get("latency_avg") or 0.0)
        packet_loss_avg = float(kpis.get("packet_loss_avg") or 0.0)
        sessions_total = int(kpis.get("sessions_total") or data.get("slices_count") or 0)
        entities_count = int(data.get("entities_count") or 0)

        aiops_counts: dict = data.get("aiops_counts") or {}
        anomalies_count = sum(int(v or 0) for v in aiops_counts.values())

        meta = _DOMAIN_META.get(domain, {"code": domain.upper(), "name": domain})

        region_cmp = RegionComparison(
            region_id=region_id,
            code=meta["code"],
            name=meta["name"],
            ric_status=_health_to_ric_status(health_avg),
            network_load=round(congestion_avg * 100, 1),
            gnodeb_count=entities_count,
            sessions_count=sessions_total,
            sla_percent=round(health_avg * 100, 1),
            avg_latency_ms=round(latency_avg, 2),
            avg_packet_loss=round(packet_loss_avg, 3),
            congestion_rate=round(congestion_avg * 100, 1),
            high_risk_sessions_count=int(data.get("active_faults_count") or 0),
            anomalies_count=anomalies_count,
        )

        slice_dist = [
            SliceDistributionPoint(
                slice_type=str(item.get("slice_type") or "eMBB"),
                sessions_count=int(item.get("entities_count") or 0),
            )
            for item in (data.get("slice_distribution") or [])
            if isinstance(item, dict)
        ]

        trend_points: list[TrendPoint] = []
        for point in (data.get("trend") or []):
            if not isinstance(point, dict):
                continue
            ts = _parse_ts(point.get("timestamp"), now)
            trend_points.append(
                TrendPoint(
                    label=ts.strftime("%H:%M"),
                    generated_at=ts,
                    sla_percent=round(float(point.get("sla_percent") or health_avg * 100), 1),
                    congestion_rate=round(float(point.get("congestion_rate") or congestion_avg * 100), 1),
                    active_alerts_count=0,
                    anomalies_count=0,
                    total_sessions=sessions_total,
                )
            )

        return RegionDashboardResponse(
            region=region_cmp,
            gnodeb_count=entities_count,
            packet_loss_avg=round(packet_loss_avg, 3),
            slice_distribution=slice_dist,
            trend=trend_points,
        )

    # ---- Sessions ----

    def list_sessions(
        self,
        *,
        region: str | None,
        risk: str | None,
        slice_type: str | None,
        page: int,
        page_size: int,
    ) -> SessionListResponse:
        try:
            data = self._get_json("/api/v1/kpis/latest", limit=500)
        except HTTPException:
            return SessionListResponse(
                items=[],
                pagination=PaginationMeta(page=page, page_size=page_size, total=0, total_pages=1),
            )

        entities: list[dict] = data.get("entities") or []
        now = datetime.now(UTC)
        sessions: list[SessionSummary] = []

        for entity in entities:
            if not isinstance(entity, dict):
                continue
            eid = str(entity.get("entity_id") or entity.get("entityId") or "").strip()
            if not eid:
                continue

            domain = str(entity.get("domain") or "ran").strip()
            region_int = _DOMAIN_TO_REGION_INT.get(domain, 3)
            kpis: dict = entity.get("kpis") or {}

            # region filter (accepts integer string or domain name)
            if region:
                if region not in (str(region_int), domain):
                    continue

            health_score = float(
                entity.get("healthScore")
                or kpis.get("derived_healthScore")
                or 0.8
            )
            latency_ms = float(
                kpis.get("latencyMs")
                or kpis.get("latency_ms")
                or kpis.get("kpi_forwardingLatencyMs")
                or kpis.get("kpi_latencyMs")
                or 5.0
            )
            packet_loss = float(
                kpis.get("packetLossPct")
                or kpis.get("kpi_packetLossPct")
                or 0.0
            )
            throughput = float(
                kpis.get("dlThroughputMbps")
                or kpis.get("kpi_dlThroughputMbps")
                or 100.0
            )

            raw_st = str(entity.get("sliceType") or entity.get("slice_type") or "eMBB")
            slice_type_val = raw_st if raw_st in _VALID_SLICE_TYPES else _DEFAULT_SLICE_TYPE

            if slice_type and slice_type_val != slice_type:
                continue

            # risk filter (derive from health score)
            if risk:
                if health_score >= 0.8:
                    entity_risk = "LOW"
                elif health_score >= 0.6:
                    entity_risk = "MEDIUM"
                elif health_score >= 0.4:
                    entity_risk = "HIGH"
                else:
                    entity_risk = "CRITICAL"
                if entity_risk != risk:
                    continue

            meta = _DOMAIN_META.get(domain, {"code": domain.upper(), "name": domain})
            ts = _parse_ts(entity.get("timestamp") or entity.get("lastUpdated"), now)

            region_summary = RegionSummary(
                id=region_int,
                code=meta["code"],
                name=meta["name"],
                ric_status=_health_to_ric_status(health_score),
                network_load=round((1.0 - health_score) * 100, 1),
                gnodeb_count=1,
            )

            sessions.append(
                SessionSummary(
                    id=_entity_int_id(eid),
                    session_code=eid,
                    region=region_summary,
                    slice_type=slice_type_val,
                    latency_ms=round(latency_ms, 2),
                    packet_loss=round(packet_loss, 4),
                    throughput_mbps=round(throughput, 2),
                    timestamp=ts,
                    prediction=None,
                )
            )

        total = len(sessions)
        start = (page - 1) * page_size
        paginated = sessions[start : start + page_size]
        total_pages = max(1, math.ceil(total / page_size)) if total else 1

        return SessionListResponse(
            items=paginated,
            pagination=PaginationMeta(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages,
            ),
        )

    def get_session(self, session_id: int) -> SessionSummary | None:
        # Build the session list and find by id
        result = self.list_sessions(region=None, risk=None, slice_type=None, page=1, page_size=500)
        for session in result.items:
            if session.id == session_id:
                return session
        return None

    # ---- Predictions ----

    def _build_prediction_list(
        self,
        region: str | None,
        risk: str | None,
    ) -> list[PredictionResponse]:
        try:
            cong_data = self._get_json("/api/v1/aiops/congestion/latest", limit=500)
            sla_data = self._get_json("/api/v1/aiops/sla/latest", limit=500)
            cls_data = self._get_json("/api/v1/aiops/slice-classification/latest", limit=500)
            kpis_data = self._get_json("/api/v1/kpis/latest", limit=500)
        except HTTPException:
            return []

        sla_by_id: dict[str, dict] = {}
        for item in (sla_data.get("items") or []):
            if isinstance(item, dict):
                eid = str(item.get("entity_id") or item.get("entityId") or "").strip()
                if eid:
                    sla_by_id[eid] = item

        cls_by_id: dict[str, dict] = {}
        for item in (cls_data.get("items") or []):
            if isinstance(item, dict):
                eid = str(item.get("entity_id") or item.get("entityId") or "").strip()
                if eid:
                    cls_by_id[eid] = item

        entities_by_id: dict[str, dict] = {}
        for entity in (kpis_data.get("entities") or []):
            if isinstance(entity, dict):
                eid = str(entity.get("entity_id") or entity.get("entityId") or "").strip()
                if eid:
                    entities_by_id[eid] = entity

        now = datetime.now(UTC)
        predictions: list[PredictionResponse] = []

        for item in (cong_data.get("items") or []):
            if not isinstance(item, dict):
                continue
            eid = str(item.get("entity_id") or item.get("entityId") or "").strip()
            if not eid:
                continue

            congestion_score = _normalize_score(
                item.get("score") or item.get("congestionScore") or item.get("value")
            )

            sla_item = sla_by_id.get(eid, {})
            sla_raw_score = _normalize_score(
                sla_item.get("score") or sla_item.get("slaScore") or sla_item.get("value")
            )
            # sla_score convention: higher is better (complement of risk)
            sla_score = round(1.0 - sla_raw_score, 3)

            entity = entities_by_id.get(eid, {})
            domain = str(entity.get("domain") or item.get("domain") or "ran").strip()
            region_int = _DOMAIN_TO_REGION_INT.get(domain, 3)

            if region and region not in (str(region_int), domain):
                continue

            health = float(entity.get("healthScore") or (1.0 - congestion_score))
            risk_level = _risk_from_scores(congestion_score, sla_raw_score)

            if risk and risk_level != risk:
                continue

            cls_item = cls_by_id.get(eid, {})
            raw_st = str(
                cls_item.get("predicted_slice_type")
                or cls_item.get("predictedSliceType")
                or entity.get("sliceType")
                or "eMBB"
            )
            predicted_type = raw_st if raw_st in _VALID_SLICE_TYPES else _DEFAULT_SLICE_TYPE
            slice_confidence = float(cls_item.get("confidence") or 0.9)

            ts = _parse_ts(item.get("timestamp"), now)
            meta = _DOMAIN_META.get(domain, {"code": domain.upper(), "name": domain})

            predictions.append(
                PredictionResponse(
                    id=_entity_int_id(f"pred:{eid}"),
                    session_id=_entity_int_id(eid),
                    session_code=eid,
                    region=RegionLite(
                        id=region_int,
                        code=meta["code"],
                        name=meta["name"],
                        ric_status=_health_to_ric_status(health),
                        network_load=round(congestion_score * 100, 1),
                    ),
                    sla_score=sla_score,
                    congestion_score=round(congestion_score, 3),
                    anomaly_score=round(max(congestion_score, sla_raw_score), 3),
                    risk_level=risk_level,
                    predicted_slice_type=predicted_type,
                    slice_confidence=round(slice_confidence, 3),
                    recommended_action=_recommended_action(risk_level),
                    model_source="bff_live_aiops",
                    predicted_at=ts,
                )
            )

        return predictions

    def list_predictions(
        self,
        *,
        region: str | None,
        risk: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[PredictionResponse], PaginationMeta]:
        all_predictions = self._build_prediction_list(region=region, risk=risk)
        total = len(all_predictions)
        start = (page - 1) * page_size
        paginated = all_predictions[start : start + page_size]
        total_pages = max(1, math.ceil(total / page_size)) if total else 1
        return paginated, PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        )

    def get_prediction(self, session_id: int) -> PredictionResponse | None:
        all_predictions = self._build_prediction_list(region=None, risk=None)
        for pred in all_predictions:
            if pred.session_id == session_id:
                return pred
        return None

    def run_prediction(self, session_id: int) -> PredictionResponse | None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "SCENARIO_B_LIVE_MODE",
                "message": (
                    "Ad-hoc prediction re-execution is not available in Scenario B live mode. "
                    "AIOps predictions are computed continuously by the AIOps workers. "
                    "View current predictions via GET /predictions."
                ),
                "source": "bff_live_state",
            },
        )

    def run_batch(self, payload: RunBatchRequest) -> list[PredictionResponse]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "SCENARIO_B_LIVE_MODE",
                "message": (
                    "Batch prediction execution is not supported in Scenario B live mode. "
                    "Set DASHBOARD_DATA_PROVIDER=temporary_mock for offline batch testing."
                ),
                "source": "bff_live_state",
            },
        )

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                name="congestion-detector",
                purpose="Congestion anomaly detection on network slices",
                implementation="ONNX FP16 (AIOps worker, live inference)",
                status="ACTIVE",
                source_notebook="mlops-tier/batch-orchestrator",
                artifact_path=None,
            ),
            ModelInfo(
                name="sla-assurance",
                purpose="SLA-at-risk prediction per network entity",
                implementation="ONNX FP16 (AIOps worker, live inference)",
                status="ACTIVE",
                source_notebook="mlops-tier/batch-orchestrator",
                artifact_path=None,
            ),
            ModelInfo(
                name="slice-classifier",
                purpose="Network slice type classification",
                implementation="ONNX FP16 (AIOps worker, live inference)",
                status="ACTIVE",
                source_notebook="mlops-tier/batch-orchestrator",
                artifact_path=None,
            ),
        ]
