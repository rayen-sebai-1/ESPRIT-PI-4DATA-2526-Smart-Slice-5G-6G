from __future__ import annotations

import json
import math
import os
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

from common.schemas import (
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
    UserOut,
)

NOW = datetime(2026, 4, 18, 21, 0, tzinfo=UTC)

SEED_USERS = [
    {
        "id": 1,
        "full_name": "Admin NeuroSlice",
        "email": "admin@neuroslice.tn",
        "password": "admin123",
        "role": "ADMIN",
        "is_active": True,
    },
    {
        "id": 2,
        "full_name": "Operateur Reseau",
        "email": "operator@neuroslice.tn",
        "password": "operator123",
        "role": "NETWORK_OPERATOR",
        "is_active": True,
    },
    {
        "id": 3,
        "full_name": "Manager National",
        "email": "manager@neuroslice.tn",
        "password": "manager123",
        "role": "NETWORK_MANAGER",
        "is_active": True,
    },
    {
        "id": 4,
        "full_name": "Data / MLOps Engineer",
        "email": "mlops@neuroslice.tn",
        "password": "mlops123",
        "role": "DATA_MLOPS_ENGINEER",
        "is_active": True,
    },
]

ASSIGNABLE_ROLES: set[str] = {"NETWORK_OPERATOR", "NETWORK_MANAGER", "DATA_MLOPS_ENGINEER"}

DEFAULT_USERS_FILE = Path(__file__).resolve().parent.parent / "data" / "users.json"
USERS_FILE = Path(os.getenv("USERS_FILE_PATH", str(DEFAULT_USERS_FILE)))

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


def _make_prediction(prediction_id: int, session_id: int, session_code: str, region: dict, slice_type: str, sla: float, congestion: float, anomaly: float, risk: str, action: str, confidence: float) -> dict:
    return {
        "id": prediction_id,
        "session_id": session_id,
        "session_code": session_code,
        "region": _region_lite(region),
        "sla_score": sla,
        "congestion_score": congestion,
        "anomaly_score": anomaly,
        "risk_level": risk,
        "predicted_slice_type": slice_type,
        "slice_confidence": confidence,
        "recommended_action": action,
        "model_source": "draft-scorer-v1",
        "predicted_at": NOW - timedelta(minutes=prediction_id * 7),
    }


SESSIONS: list[dict] = []
PREDICTIONS: list[dict] = []
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

        sla_score = round(max(0.1, 1 - region["sla_percent"] / 100 + index * 0.03), 2)
        congestion_score = round(min(0.98, region["congestion_rate"] / 100 + index * 0.025), 2)
        anomaly_score = round(min(0.95, region["anomalies_count"] * 0.12 + index * 0.05), 2)
        action = (
            "Reequilibrer la charge et surveiller la region."
            if risk in {"HIGH", "CRITICAL"}
            else "Maintenir une surveillance standard."
        )
        prediction = _make_prediction(
            prediction_id=prediction_id,
            session_id=session_id,
            session_code=f"NS-{region['code']}-{index + 1:03d}",
            region=region,
            slice_type=slice_type,
            sla=sla_score,
            congestion=congestion_score,
            anomaly=anomaly_score,
            risk=risk,
            action=action,
            confidence=round(0.82 + (index % 4) * 0.04, 2),
        )
        session = {
            "id": session_id,
            "session_code": f"NS-{region['code']}-{index + 1:03d}",
            "region": _region_summary(region),
            "slice_type": slice_type,
            "latency_ms": latency,
            "packet_loss": packet_loss,
            "throughput_mbps": throughput,
            "timestamp": NOW - timedelta(minutes=session_id * 9),
            "prediction": PredictionSummary(**prediction),
        }
        SESSIONS.append(session)
        PREDICTIONS.append(prediction)
        prediction_id += 1
        session_id += 1


def _paginate(items: list, page: int, page_size: int) -> PaginationMeta:
    total = len(items)
    total_pages = max(1, math.ceil(total / page_size))
    return PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages)


def _ensure_users_file() -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not USERS_FILE.exists():
        USERS_FILE.write_text(json.dumps(SEED_USERS, indent=2), encoding="utf-8")


def _load_users() -> list[dict]:
    _ensure_users_file()
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        USERS_FILE.write_text(json.dumps(SEED_USERS, indent=2), encoding="utf-8")
        return deepcopy(SEED_USERS)


def _save_users(users: list[dict]) -> None:
    _ensure_users_file()
    USERS_FILE.write_text(json.dumps(users, indent=2), encoding="utf-8")


def _public_user(user: dict) -> UserOut:
    return UserOut(**{key: value for key, value in user.items() if key != "password"})


def find_user_by_email(email: str) -> UserOut | None:
    for user in _load_users():
        if user["email"].lower() == email.lower():
            return _public_user(user)
    return None


def verify_user(email: str, password: str) -> UserOut | None:
    for user in _load_users():
        if user["email"].lower() == email.lower() and user["password"] == password and user["is_active"]:
            return _public_user(user)
    return None


def list_users() -> list[UserOut]:
    return [_public_user(user) for user in _load_users()]


def create_user(full_name: str, email: str, password: str, role: str) -> UserOut:
    users = _load_users()
    normalized_email = email.strip().lower()
    normalized_name = full_name.strip()

    if not normalized_name:
        raise ValueError("Le nom complet est obligatoire.")
    if role not in ASSIGNABLE_ROLES:
        raise ValueError("Role invalide. Un admin ne peut pas etre cree via cette route.")
    if any(user["email"].lower() == normalized_email for user in users):
        raise ValueError("Un compte existe deja avec cet email.")

    next_id = max((int(user["id"]) for user in users), default=0) + 1
    new_user = {
        "id": next_id,
        "full_name": normalized_name,
        "email": normalized_email,
        "password": password,
        "role": role,
        "is_active": True,
    }
    users.append(new_user)
    _save_users(users)
    return _public_user(new_user)


def update_user(
    user_id: int,
    full_name: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    password: str | None = None,
) -> UserOut:
    users = _load_users()
    target = next((user for user in users if int(user["id"]) == int(user_id)), None)
    if target is None:
        raise LookupError("Utilisateur introuvable.")
    if target["role"] == "ADMIN" and role is not None and role != "ADMIN":
        raise ValueError("Le role d'un administrateur ne peut pas etre modifie.")
    if role is not None and role not in ASSIGNABLE_ROLES and role != target["role"]:
        raise ValueError("Role invalide.")
    if full_name is not None:
        cleaned = full_name.strip()
        if not cleaned:
            raise ValueError("Le nom complet est obligatoire.")
        target["full_name"] = cleaned
    if role is not None:
        target["role"] = role
    if is_active is not None:
        if target["role"] == "ADMIN" and is_active is False:
            raise ValueError("Un administrateur ne peut pas etre desactive.")
        target["is_active"] = bool(is_active)
    if password is not None:
        target["password"] = password
    _save_users(users)
    return _public_user(target)


def delete_user(user_id: int) -> None:
    users = _load_users()
    target = next((user for user in users if int(user["id"]) == int(user_id)), None)
    if target is None:
        raise LookupError("Utilisateur introuvable.")
    if target["role"] == "ADMIN":
        raise ValueError("Un administrateur ne peut pas etre supprime.")
    remaining = [user for user in users if int(user["id"]) != int(user_id)]
    _save_users(remaining)


def list_models_catalog() -> list[ModelInfo]:
    return [
        ModelInfo(
            name="draft-auth-aware-scorer",
            purpose="Scoring demo pour le dashboard draft",
            implementation="In-memory deterministic logic",
            status="ACTIVE",
            source_notebook="Aucun - version draft frontend/backend",
            artifact_path=None,
        ),
        ModelInfo(
            name="regional-risk-prioritizer",
            purpose="Priorisation simple des regions et sessions a surveiller",
            implementation="Rules + weighted regional KPIs",
            status="ACTIVE",
            source_notebook="Aucun - logique de demonstration",
            artifact_path=None,
        ),
    ]


def list_sessions(region: str | None, risk: str | None, slice_type: str | None, page: int, page_size: int) -> SessionListResponse:
    items = deepcopy(SESSIONS)
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


def get_session(session_id: int) -> SessionSummary | None:
    for session in SESSIONS:
        if session["id"] == session_id:
            return SessionSummary(**deepcopy(session))
    return None


def list_predictions(region: str | None, risk: str | None, page: int, page_size: int):
    items = deepcopy(PREDICTIONS)
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


def get_prediction(session_id: int) -> PredictionResponse | None:
    for prediction in PREDICTIONS:
        if prediction["session_id"] == session_id:
            return PredictionResponse(**deepcopy(prediction))
    return None


def run_prediction(session_id: int) -> PredictionResponse | None:
    for prediction in PREDICTIONS:
        if prediction["session_id"] == session_id:
            prediction["predicted_at"] = datetime.now(UTC)
            prediction["congestion_score"] = round(min(0.99, prediction["congestion_score"] + 0.01), 2)
            prediction["sla_score"] = round(min(0.99, prediction["sla_score"] + 0.01), 2)
            if prediction["congestion_score"] >= 0.7 or prediction["sla_score"] >= 0.55:
                prediction["risk_level"] = "HIGH" if prediction["risk_level"] != "CRITICAL" else "CRITICAL"
            for session in SESSIONS:
                if session["id"] == session_id:
                    session["prediction"] = PredictionSummary(**prediction)
                    break
            return PredictionResponse(**deepcopy(prediction))
    return None


def run_batch(payload: RunBatchRequest) -> list[PredictionResponse]:
    target_sessions = SESSIONS
    if payload.region_id is not None:
        target_sessions = [session for session in SESSIONS if session["region"].id == payload.region_id]
    results: list[PredictionResponse] = []
    for session in target_sessions[: payload.limit]:
        prediction = run_prediction(session["id"])
        if prediction is not None:
            results.append(prediction)
    return results


def national_dashboard() -> NationalDashboardResponse:
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


def region_dashboard(region_id: int) -> RegionDashboardResponse | None:
    region = next((item for item in REGIONS if item["region_id"] == region_id), None)
    if region is None:
        return None
    sessions = [item for item in SESSIONS if item["region"].id == region_id]
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
