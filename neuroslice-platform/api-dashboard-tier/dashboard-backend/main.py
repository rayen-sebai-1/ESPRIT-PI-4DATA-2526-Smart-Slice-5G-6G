from __future__ import annotations

import json
import logging
import os
import time
from datetime import UTC, datetime
from typing import Annotated, Any

import httpx
import redis
import uuid

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import check_database_connection, get_db
from mlops import MlopsService, get_mlops_service
from mlops_ops import MlopsOpsService, background_execute_run
from mlops_orchestration import MlopsOrchestrationService, background_execute_orchestration_run
from schemas import (
    AgenticHealthResponse,
    AlertAcknowledgePayload,
    AlertAcknowledgementResponse,
    AuthenticatedPrincipal,
    DashboardBookmarkPayload,
    DashboardBookmarkResponse,
    DashboardPreferencesPayload,
    DashboardPreferencesResponse,
    MlopsActionResponse,
    MlopsArtifactStatus,
    MlopsModelHealth,
    MlopsOrchestrationRunLogsResponse,
    MlopsOrchestrationRunRequest,
    MlopsOrchestrationRunResponse,
    MlopsOverview,
    MlopsActionDefinition,
    MlopsPipelineConfigResponse,
    MlopsPipelineRunLogsResponse,
    MlopsPipelineRunResponse,
    MlopsPredictionMonitoringResponse,
    MlopsPromoteRequest,
    MlopsPromotionEvent,
    MlopsRetrainingRequest,
    MlopsRetrainingRequestListResponse,
    MlopsRollbackRequest,
    MlopsRunSummary,
    MlopsToolsHealthResponse,
    MlopsToolsResponse,
    ModelInfo,
    PredictionListResponse,
    PredictionResponse,
    RunBatchRequest,
    SessionListResponse,
    SessionSummary,
)
from service import DashboardService, get_current_user, get_dashboard_provider, get_dashboard_service, require_roles


def _get_root_cause_url() -> str:
    return os.getenv("ROOT_CAUSE_AGENT_URL", "http://root-cause:7005").rstrip("/")


def _get_copilot_url() -> str:
    return os.getenv("COPILOT_AGENT_URL", "http://copilot-agent:7006").rstrip("/")


def get_mlops_ops_service(db: Annotated[Session, Depends(get_db)]) -> MlopsOpsService:
    return MlopsOpsService(db)

def get_mlops_orchestration_service(db: Annotated[Session, Depends(get_db)]) -> MlopsOrchestrationService:
    return MlopsOrchestrationService(db)

app = FastAPI(title="NeuroSlice Dashboard Backend", version="2.0.0")
logger = logging.getLogger("dashboard-backend")

dashboard_reader_roles = ("ADMIN", "NETWORK_OPERATOR", "NETWORK_MANAGER")
prediction_reader_roles = ("ADMIN", "NETWORK_OPERATOR", "NETWORK_MANAGER", "DATA_MLOPS_ENGINEER")
writer_roles = ("ADMIN", "NETWORK_OPERATOR")
mlops_reader_roles = ("ADMIN", "DATA_MLOPS_ENGINEER", "NETWORK_MANAGER")
mlops_writer_roles = ("ADMIN", "DATA_MLOPS_ENGINEER")
runtime_reader_roles = ("ADMIN", "NETWORK_MANAGER", "DATA_MLOPS_ENGINEER", "NETWORK_OPERATOR")
runtime_controlled_services = (
    "congestion-detector",
    "sla-assurance",
    "slice-classifier",
    "aiops-drift-monitor",
    "mlops-drift-monitor",
)

dashboard_requests_total = Counter(
    "neuroslice_dashboard_requests_total",
    "Total dashboard backend requests",
    ["route", "method", "status"],
)
dashboard_request_latency_seconds = Histogram(
    "neuroslice_dashboard_request_latency_seconds",
    "Dashboard backend request latency",
    ["route", "method"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
)
dashboard_mlops_pipeline_requests_total = Counter(
    "neuroslice_dashboard_mlops_pipeline_requests_total",
    "Total MLOps pipeline trigger requests received by dashboard-backend",
    ["status"],
)
dashboard_auth_failures_total = Counter(
    "neuroslice_dashboard_auth_failures_total",
    "Total dashboard authentication and authorization failures",
)


def _route_label(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return str(path or request.url.path)


@app.middleware("http")
async def dashboard_metrics_middleware(request: Request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        route = _route_label(request)
        duration = time.perf_counter() - started
        dashboard_requests_total.labels(route=route, method=request.method, status="500").inc()
        dashboard_request_latency_seconds.labels(route=route, method=request.method).observe(duration)
        raise

    route = _route_label(request)
    status_code = str(response.status_code)
    duration = time.perf_counter() - started
    dashboard_requests_total.labels(route=route, method=request.method, status=status_code).inc()
    dashboard_request_latency_seconds.labels(route=route, method=request.method).observe(duration)
    if response.status_code in {401, 403}:
        dashboard_auth_failures_total.inc()
    return response


class RuntimeServicePatchRequest(BaseModel):
    enabled: bool | None = None
    mode: str | None = None
    reason: str | None = None


def _runtime_key(service_name: str, suffix: str) -> str:
    return f"runtime:service:{service_name}:{suffix}"


def _runtime_redis_client() -> redis.Redis:
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        decode_responses=True,
    )


_MLOPS_REQUEST_INDEX_KEY = "mlops:requests:index"
_MLOPS_REQUEST_PREFIX = "mlops:request:"
_MLOPS_MODEL_PENDING_PREFIX = "mlops:requests:pending:model:"
_MLOPS_RUNNING_SET_KEY = "mlops:requests:running"
_MLOPS_DECISION_LOCK_KEY = "mlops:requests:decision_lock"
_MLOPS_COOLDOWN_PREFIX = "mlops:cooldown:last_executed:"
_MLOPS_MODEL_LOCK_PREFIX = "mlops:lock:"

_MLOPS_REQUEST_ACTION_BY_MODEL: dict[str, str] = {
    "congestion-5g": "pipeline_congestion_5g",
    "sla-5g": "pipeline_sla_5g",
    "slice-type-5g": "pipeline_slice_type_5g",
}

_MLOPS_INTERNAL_TO_PUBLIC_MODEL: dict[str, str] = {
    "congestion_5g": "congestion-5g",
    "sla_5g": "sla-5g",
    "slice_type_5g": "slice-type-5g",
}

_MLOPS_PUBLIC_TO_INTERNAL_MODEL: dict[str, str] = {
    value: key for key, value in _MLOPS_INTERNAL_TO_PUBLIC_MODEL.items()
}

try:
    _MAX_PARALLEL_TRAINING = max(1, int(os.getenv("MAX_PARALLEL_TRAINING", "1")))
except ValueError:
    _MAX_PARALLEL_TRAINING = 1

try:
    _MLOPS_RETRAIN_COOLDOWN_MINUTES = max(0, int(os.getenv("MLOPS_RETRAIN_COOLDOWN_MINUTES", "30")))
except ValueError:
    _MLOPS_RETRAIN_COOLDOWN_MINUTES = 30

try:
    _MLOPS_RUNNER_TIMEOUT_SECONDS = max(
        60,
        int(os.getenv("MLOPS_ORCHESTRATION_TIMEOUT_SECONDS", "7200")),
    )
except ValueError:
    _MLOPS_RUNNER_TIMEOUT_SECONDS = 7200

def _parse_bool(value: str | None, *, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _runtime_default_mode(enabled: bool) -> str:
    return "auto" if enabled else "disabled"


def _read_runtime_service_state(service_name: str) -> dict[str, Any]:
    if service_name not in runtime_controlled_services:
        raise HTTPException(status_code=404, detail=f"Unknown runtime service '{service_name}'.")

    client = _runtime_redis_client()
    enabled = _parse_bool(client.get(_runtime_key(service_name, "enabled")), default=True)
    mode = client.get(_runtime_key(service_name, "mode")) or _runtime_default_mode(enabled)
    updated_at = client.get(_runtime_key(service_name, "updated_at"))
    updated_by = client.get(_runtime_key(service_name, "updated_by")) or "system"
    reason = client.get(_runtime_key(service_name, "reason")) or ""
    return {
        "service_name": service_name,
        "enabled": enabled,
        "mode": mode,
        "updated_at": updated_at,
        "updated_by": updated_by,
        "reason": reason,
    }


def _can_write_runtime(service_name: str, principal: AuthenticatedPrincipal) -> bool:
    if principal.role == "ADMIN":
        return True
    if principal.role == "DATA_MLOPS_ENGINEER":
        return service_name in runtime_controlled_services
    if principal.role == "NETWORK_OPERATOR":
        return service_name in {"congestion-detector", "sla-assurance", "slice-classifier", "aiops-drift-monitor"}
    return False


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _request_key(request_id: str) -> str:
    return f"{_MLOPS_REQUEST_PREFIX}{request_id}"


def _request_pending_key(model_internal: str) -> str:
    return f"{_MLOPS_MODEL_PENDING_PREFIX}{model_internal}"


def _model_lock_key(model: str) -> str:
    return f"{_MLOPS_MODEL_LOCK_PREFIX}{model}"


def _request_cooldown_key(model: str) -> str:
    return f"{_MLOPS_COOLDOWN_PREFIX}{model}"


def _request_model_internal(raw: dict[str, Any]) -> str:
    value = str(raw.get("model_internal") or "").strip()
    if value:
        return value
    model = str(raw.get("model") or "").strip()
    if model in _MLOPS_PUBLIC_TO_INTERNAL_MODEL:
        return _MLOPS_PUBLIC_TO_INTERNAL_MODEL[model]
    return model


def _request_model_public(raw: dict[str, Any]) -> str:
    value = str(raw.get("model") or "").strip()
    if value:
        return value
    internal = str(raw.get("model_internal") or "").strip()
    if internal in _MLOPS_INTERNAL_TO_PUBLIC_MODEL:
        return _MLOPS_INTERNAL_TO_PUBLIC_MODEL[internal]
    return internal


def _normalize_retraining_request(raw: dict[str, Any]) -> MlopsRetrainingRequest:
    normalized = dict(raw)
    normalized["id"] = str(raw.get("id") or "")
    normalized["model"] = _request_model_public(raw)
    normalized["model_internal"] = _request_model_internal(raw)
    normalized["pipeline_action"] = raw.get("pipeline_action") or _MLOPS_REQUEST_ACTION_BY_MODEL.get(normalized["model"])
    normalized["reason"] = str(raw.get("reason") or "drift_detected")
    normalized["anomaly_count"] = int(raw.get("anomaly_count") or 0)
    normalized["threshold"] = int(raw.get("threshold") or 0)
    normalized["status"] = str(raw.get("status") or "pending_approval")
    normalized["created_at"] = str(raw.get("created_at") or _now_iso())
    normalized["updated_at"] = str(raw.get("updated_at") or normalized["created_at"])
    normalized["approved_by"] = raw.get("approved_by")
    normalized["approved_at"] = raw.get("approved_at")
    normalized["executed_by"] = raw.get("executed_by")
    normalized["executed_at"] = raw.get("executed_at")
    normalized["completed_at"] = raw.get("completed_at")
    normalized["execution_run_id"] = raw.get("execution_run_id")
    normalized["execution_detail"] = raw.get("execution_detail")
    return MlopsRetrainingRequest.model_validate(normalized)


def _load_retraining_request(client: redis.Redis, request_id: str) -> dict[str, Any]:
    raw = client.get(_request_key(request_id))
    if raw is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retraining request introuvable.")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Corrupted retraining request payload.") from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid retraining request payload type.")
    return value


def _save_retraining_request(client: redis.Redis, request: dict[str, Any]) -> None:
    request["updated_at"] = _now_iso()
    request_id = str(request.get("id") or "")
    if not request_id:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Missing retraining request id.")
    client.set(_request_key(request_id), json.dumps(request))


def _release_running_controls(client: redis.Redis, request: dict[str, Any]) -> None:
    request_id = str(request.get("id") or "")
    model = _request_model_public(request)
    if request_id:
        client.srem(_MLOPS_RUNNING_SET_KEY, request_id)
    if model:
        lock_key = _model_lock_key(model)
        owner = client.get(lock_key)
        if owner == request_id:
            client.delete(lock_key)


def _runner_headers() -> dict[str, str]:
    token = (os.getenv("MLOPS_RUNNER_TOKEN") or "").strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _runner_url() -> str:
    return (os.getenv("MLOPS_RUNNER_URL", "http://mlops-runner:8020").rstrip("/"))


def _execute_retraining_request_background(request_id: str) -> None:
    client = _runtime_redis_client()
    request = _load_retraining_request(client, request_id)
    action = str(
        request.get("pipeline_action")
        or _MLOPS_REQUEST_ACTION_BY_MODEL.get(_request_model_public(request))
        or ""
    ).strip()

    if not action:
        logger.warning("Retraining request %s failed before execution: missing pipeline action mapping.", request_id)
        request["status"] = "failed"
        request["completed_at"] = _now_iso()
        request["execution_detail"] = "Missing pipeline action mapping."
        _save_retraining_request(client, request)
        _release_running_controls(client, request)
        return

    payload = {
        "action": action,
        "trigger_source": "manual",
        "parameters": {
            "DRIFT_ANOMALY_COUNT": str(int(request.get("anomaly_count") or 0)),
            "MLOPS_REQUEST_ID": str(request_id),
        },
    }

    status_value = "failed"
    detail = "mlops-runner request failed"
    try:
        logger.info(
            "Executing retraining request %s model=%s action=%s anomaly_count=%s",
            request_id,
            _request_model_public(request),
            action,
            request.get("anomaly_count"),
        )
        with httpx.Client(timeout=_MLOPS_RUNNER_TIMEOUT_SECONDS + 30) as http_client:
            response = http_client.post(
                f"{_runner_url()}/run-action",
                json=payload,
                headers=_runner_headers(),
            )
        if response.status_code >= 400:
            detail = f"mlops-runner returned HTTP {response.status_code}"
        else:
            data = response.json()
            timed_out = bool(data.get("timed_out"))
            accepted = bool(data.get("accepted"))
            exit_code = data.get("exit_code")
            if timed_out:
                status_value = "failed"
                detail = "Runner execution timed out."
            elif accepted and isinstance(exit_code, int) and exit_code == 0:
                status_value = "completed"
                detail = "Training completed successfully."
            elif accepted and isinstance(exit_code, int):
                status_value = "failed"
                detail = f"Training failed with exit code {exit_code}."
            else:
                status_value = "failed"
                detail = str(data.get("detail") or "Runner reported failure.")
    except Exception as exc:  # noqa: BLE001
        status_value = "failed"
        detail = f"Runner call exception: {type(exc).__name__}: {exc}"
    finally:
        request = _load_retraining_request(client, request_id)
        request["status"] = status_value
        request["completed_at"] = _now_iso()
        request["execution_detail"] = detail
        if status_value == "completed":
            model = _request_model_public(request)
            client.set(_request_cooldown_key(model), str(time.time()))
            model_internal = _request_model_internal(request)
            if model_internal:
                client.srem(_request_pending_key(model_internal), request_id)
        _save_retraining_request(client, request)
        _release_running_controls(client, request)
        logger.info(
            "Retraining request %s finished status=%s detail=%s",
            request_id,
            status_value,
            detail,
        )

@app.get("/health")
def health() -> dict[str, str]:
    try:
        check_database_connection()
        database_state = "up"
        service_state = "ok"
    except Exception:
        database_state = "down"
        service_state = "degraded"

    return {
        "status": service_state,
        "service": "dashboard-backend",
        "database": database_state,
        "provider": get_dashboard_provider().name,
    }


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/dashboard/national", tags=["dashboard"])
def get_national_dashboard(
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*dashboard_reader_roles))],
):
    return dashboard_service.provider.get_national_dashboard()


@app.get("/dashboard/region/{region_id}", tags=["dashboard"])
def get_region_dashboard(
    region_id: int,
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*dashboard_reader_roles))],
):
    response = dashboard_service.provider.get_region_dashboard(region_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region introuvable.")
    return response


@app.get("/dashboard/preferences/me", response_model=DashboardPreferencesResponse, tags=["dashboard"])
def get_my_preferences(
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
    current_user: Annotated[AuthenticatedPrincipal, Depends(get_current_user)],
) -> DashboardPreferencesResponse:
    return dashboard_service.get_preferences(current_user)


@app.put("/dashboard/preferences/me", response_model=DashboardPreferencesResponse, tags=["dashboard"])
def update_my_preferences(
    payload: DashboardPreferencesPayload,
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
    current_user: Annotated[AuthenticatedPrincipal, Depends(get_current_user)],
) -> DashboardPreferencesResponse:
    return dashboard_service.update_preferences(current_user, payload)


@app.get("/dashboard/bookmarks", response_model=list[DashboardBookmarkResponse], tags=["dashboard"])
def list_my_bookmarks(
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
    current_user: Annotated[AuthenticatedPrincipal, Depends(get_current_user)],
) -> list[DashboardBookmarkResponse]:
    return dashboard_service.list_bookmarks(current_user)


@app.post("/dashboard/bookmarks", response_model=DashboardBookmarkResponse, status_code=status.HTTP_201_CREATED, tags=["dashboard"])
def create_bookmark(
    payload: DashboardBookmarkPayload,
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
    current_user: Annotated[AuthenticatedPrincipal, Depends(get_current_user)],
) -> DashboardBookmarkResponse:
    return dashboard_service.save_bookmark(current_user, payload)


@app.delete("/dashboard/bookmarks", status_code=status.HTTP_204_NO_CONTENT, tags=["dashboard"])
def delete_bookmark(
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
    current_user: Annotated[AuthenticatedPrincipal, Depends(get_current_user)],
    bookmark_id: Annotated[int, Query(ge=1)],
) -> Response:
    dashboard_service.delete_bookmark(current_user, bookmark_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post(
    "/dashboard/alerts/{alert_key}/acknowledge",
    response_model=AlertAcknowledgementResponse,
    tags=["dashboard"],
)
def acknowledge_alert(
    alert_key: str,
    payload: AlertAcknowledgePayload,
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
    current_user: Annotated[AuthenticatedPrincipal, Depends(get_current_user)],
) -> AlertAcknowledgementResponse:
    return dashboard_service.acknowledge_alert(current_user, alert_key=alert_key, note=payload.note)


@app.get("/sessions", response_model=SessionListResponse, tags=["sessions"])
def get_sessions(
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*dashboard_reader_roles))],
    region: str | None = Query(default=None),
    risk: str | None = Query(default=None),
    slice: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> SessionListResponse:
    return dashboard_service.provider.list_sessions(
        region=region,
        risk=risk,
        slice_type=slice,
        page=page,
        page_size=page_size,
    )


@app.get("/sessions/{session_id}", response_model=SessionSummary, tags=["sessions"])
def get_session_by_id(
    session_id: int,
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*dashboard_reader_roles))],
) -> SessionSummary:
    session = dashboard_service.provider.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session introuvable.")
    return session


@app.get("/predictions", response_model=PredictionListResponse, tags=["predictions"])
def get_predictions(
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*prediction_reader_roles))],
    region: str | None = Query(default=None),
    risk: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PredictionListResponse:
    items, pagination = dashboard_service.provider.list_predictions(
        region=region,
        risk=risk,
        page=page,
        page_size=page_size,
    )
    return PredictionListResponse(items=items, pagination=pagination)


@app.get("/models", response_model=list[ModelInfo], tags=["predictions"])
def get_models_catalog(
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*prediction_reader_roles))],
) -> list[ModelInfo]:
    return dashboard_service.provider.list_models()


@app.get("/predictions/{session_id}", response_model=PredictionResponse, tags=["predictions"])
def get_prediction_by_session(
    session_id: int,
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*prediction_reader_roles))],
) -> PredictionResponse:
    prediction = dashboard_service.provider.get_prediction(session_id)
    if prediction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction introuvable.")
    return prediction


@app.post("/predictions/run/{session_id}", response_model=PredictionResponse, tags=["predictions"])
def rerun_prediction(
    session_id: int,
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*writer_roles))],
) -> PredictionResponse:
    prediction = dashboard_service.provider.run_prediction(session_id)
    if prediction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session introuvable.")
    return prediction


@app.post("/predictions/run-batch", response_model=list[PredictionResponse], tags=["predictions"])
def rerun_batch(
    payload: RunBatchRequest,
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*writer_roles))],
) -> list[PredictionResponse]:
    return dashboard_service.provider.run_batch(payload)


@app.get("/mlops/overview", response_model=MlopsOverview, tags=["mlops"])
def get_mlops_overview(
    mlops: Annotated[MlopsService, Depends(get_mlops_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
) -> MlopsOverview:
    return mlops.get_overview()


@app.get("/mlops/models", response_model=list[MlopsModelHealth], tags=["mlops"])
def list_mlops_models(
    mlops: Annotated[MlopsService, Depends(get_mlops_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
) -> list[MlopsModelHealth]:
    return mlops.list_models()


@app.get("/mlops/models/{model_name}", response_model=MlopsModelHealth, tags=["mlops"])
def get_mlops_model(
    model_name: str,
    mlops: Annotated[MlopsService, Depends(get_mlops_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
) -> MlopsModelHealth:
    detail = mlops.get_model_detail(model_name)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model introuvable.")
    return detail


@app.get("/mlops/runs", response_model=list[MlopsRunSummary], tags=["mlops"])
def list_mlops_runs(
    mlops: Annotated[MlopsService, Depends(get_mlops_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[MlopsRunSummary]:
    return mlops.list_runs(limit=limit)


@app.get("/mlops/artifacts", response_model=list[MlopsArtifactStatus], tags=["mlops"])
def list_mlops_artifacts(
    mlops: Annotated[MlopsService, Depends(get_mlops_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
) -> list[MlopsArtifactStatus]:
    return mlops.list_artifacts()


@app.get("/mlops/promotions", response_model=list[MlopsPromotionEvent], tags=["mlops"])
def list_mlops_promotions(
    mlops: Annotated[MlopsService, Depends(get_mlops_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[MlopsPromotionEvent]:
    return mlops.list_promotions(limit=limit)


@app.get(
    "/mlops/monitoring/predictions",
    response_model=MlopsPredictionMonitoringResponse,
    tags=["mlops"],
)
def get_mlops_prediction_monitoring(
    mlops: Annotated[MlopsService, Depends(get_mlops_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
    model: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> MlopsPredictionMonitoringResponse:
    return mlops.get_prediction_monitoring(model=model, limit=limit)


@app.post("/mlops/promote", response_model=MlopsActionResponse, tags=["mlops"])
def promote_mlops_model(
    payload: MlopsPromoteRequest,
    mlops: Annotated[MlopsService, Depends(get_mlops_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_writer_roles))],
) -> MlopsActionResponse:
    return mlops.promote_model(payload)


@app.post("/mlops/rollback", response_model=MlopsActionResponse, tags=["mlops"])
def rollback_mlops_model(
    payload: MlopsRollbackRequest,
    mlops: Annotated[MlopsService, Depends(get_mlops_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_writer_roles))],
) -> MlopsActionResponse:
    return mlops.rollback_model(payload)


@app.get("/mlops/requests", response_model=MlopsRetrainingRequestListResponse, tags=["mlops"])
def list_mlops_retraining_requests(
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
) -> MlopsRetrainingRequestListResponse:
    client = _runtime_redis_client()
    request_ids = client.zrevrange(_MLOPS_REQUEST_INDEX_KEY, 0, max(0, limit - 1))
    allowed_statuses = {part.strip() for part in (status_filter or "").split(",") if part.strip()}

    items: list[MlopsRetrainingRequest] = []
    for request_id in request_ids:
        raw = client.get(_request_key(request_id))
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        normalized = _normalize_retraining_request(parsed)
        if allowed_statuses and normalized.status not in allowed_statuses:
            continue
        items.append(normalized)

    return MlopsRetrainingRequestListResponse(count=len(items), items=items)


@app.get("/mlops/requests/{request_id}", response_model=MlopsRetrainingRequest, tags=["mlops"])
def get_mlops_retraining_request(
    request_id: str,
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
) -> MlopsRetrainingRequest:
    client = _runtime_redis_client()
    request = _load_retraining_request(client, request_id)
    return _normalize_retraining_request(request)


@app.post("/mlops/requests/{request_id}/approve", response_model=MlopsRetrainingRequest, tags=["mlops"])
def approve_mlops_retraining_request(
    request_id: str,
    current_user: Annotated[AuthenticatedPrincipal, Depends(require_roles("ADMIN"))],
) -> MlopsRetrainingRequest:
    client = _runtime_redis_client()
    request = _load_retraining_request(client, request_id)
    current_status = str(request.get("status") or "")
    if current_status != "pending_approval":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only pending requests can be approved (current status: {current_status}).")

    now_iso = _now_iso()
    request["status"] = "approved"
    request["approved_by"] = current_user.email
    request["approved_at"] = now_iso
    request["execution_detail"] = "Approved by admin; waiting for execution."
    _save_retraining_request(client, request)
    logger.info("Retraining request %s approved by %s", request_id, current_user.email)
    return _normalize_retraining_request(request)


@app.post("/mlops/requests/{request_id}/reject", response_model=MlopsRetrainingRequest, tags=["mlops"])
def reject_mlops_retraining_request(
    request_id: str,
    current_user: Annotated[AuthenticatedPrincipal, Depends(require_roles("ADMIN"))],
) -> MlopsRetrainingRequest:
    client = _runtime_redis_client()
    request = _load_retraining_request(client, request_id)
    current_status = str(request.get("status") or "")
    if current_status not in {"pending_approval", "approved"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot reject request in status: {current_status}.")

    request["status"] = "rejected"
    request["execution_detail"] = f"Rejected by {current_user.email}."
    model_internal = _request_model_internal(request)
    if model_internal:
        client.srem(_request_pending_key(model_internal), request_id)
    _save_retraining_request(client, request)
    logger.info("Retraining request %s rejected by %s", request_id, current_user.email)
    return _normalize_retraining_request(request)


@app.post(
    "/mlops/requests/{request_id}/execute",
    response_model=MlopsRetrainingRequest,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["mlops"],
)
def execute_mlops_retraining_request(
    request_id: str,
    background_tasks: BackgroundTasks,
    current_user: Annotated[AuthenticatedPrincipal, Depends(require_roles("ADMIN"))],
) -> MlopsRetrainingRequest:
    client = _runtime_redis_client()
    decision_lock = client.lock(_MLOPS_DECISION_LOCK_KEY, timeout=10, blocking_timeout=2)
    if not decision_lock.acquire(blocking=True):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Another execution decision is in progress. Retry.")
    try:
        request = _load_retraining_request(client, request_id)
        current_status = str(request.get("status") or "")
        if current_status != "approved":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Request must be approved before execution (current status: {current_status}).")

        model = _request_model_public(request)
        model_internal = _request_model_internal(request)
        lock_key = _model_lock_key(model)
        cooldown_key = _request_cooldown_key(model)

        cooldown_sec = _MLOPS_RETRAIN_COOLDOWN_MINUTES * 60
        now_ts = time.time()
        cooldown_last = client.get(cooldown_key)
        if cooldown_last is not None:
            try:
                elapsed = now_ts - float(cooldown_last)
            except ValueError:
                elapsed = cooldown_sec + 1
            if elapsed < cooldown_sec:
                request["status"] = "skipped"
                request["execution_detail"] = (
                    f"Skipped due to cooldown ({_MLOPS_RETRAIN_COOLDOWN_MINUTES} minutes)."
                )
                _save_retraining_request(client, request)
                logger.warning(
                    "Retraining request %s skipped due to cooldown model=%s cooldown_minutes=%d",
                    request_id,
                    model,
                    _MLOPS_RETRAIN_COOLDOWN_MINUTES,
                )
                if model_internal:
                    client.srem(_request_pending_key(model_internal), request_id)
                return _normalize_retraining_request(request)

        running_count = int(client.scard(_MLOPS_RUNNING_SET_KEY) or 0)
        if running_count >= _MAX_PARALLEL_TRAINING:
            request["status"] = "skipped"
            request["execution_detail"] = (
                f"Skipped due to global concurrency limit ({_MAX_PARALLEL_TRAINING})."
            )
            _save_retraining_request(client, request)
            logger.warning(
                "Retraining request %s skipped by global concurrency limit running=%d limit=%d",
                request_id,
                running_count,
                _MAX_PARALLEL_TRAINING,
            )
            return _normalize_retraining_request(request)

        lock_ttl = _MLOPS_RUNNER_TIMEOUT_SECONDS + 300
        lock_acquired = bool(client.set(lock_key, request_id, nx=True, ex=lock_ttl))
        if not lock_acquired:
            request["status"] = "skipped"
            request["execution_detail"] = "Skipped because another training for this model is already running."
            _save_retraining_request(client, request)
            logger.warning(
                "Retraining request %s skipped because model lock is active for model=%s",
                request_id,
                model,
            )
            return _normalize_retraining_request(request)

        run_ref = str(uuid.uuid4())
        now_iso = _now_iso()
        client.sadd(_MLOPS_RUNNING_SET_KEY, request_id)
        request["status"] = "running"
        request["executed_by"] = current_user.email
        request["executed_at"] = now_iso
        request["execution_run_id"] = run_ref
        request["execution_detail"] = "Execution accepted by dashboard control plane."
        _save_retraining_request(client, request)
        logger.info(
            "Retraining request %s execution accepted by %s model=%s run_ref=%s",
            request_id,
            current_user.email,
            model,
            run_ref,
        )
        background_tasks.add_task(_execute_retraining_request_background, request_id)
        return _normalize_retraining_request(request)
    finally:
        try:
            decision_lock.release()
        except Exception:
            pass


@app.get("/mlops/tools", response_model=MlopsToolsResponse, tags=["mlops-ops"])
def list_mlops_tools(
    ops: Annotated[MlopsOpsService, Depends(get_mlops_ops_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
) -> MlopsToolsResponse:
    return ops.list_tools()


@app.get("/mlops/tools/health", response_model=MlopsToolsHealthResponse, tags=["mlops-ops"])
def check_mlops_tools_health(
    ops: Annotated[MlopsOpsService, Depends(get_mlops_ops_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
) -> MlopsToolsHealthResponse:
    return ops.check_tool_health()


@app.post(
    "/mlops/pipeline/run",
    response_model=MlopsPipelineRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["mlops-ops"],
)
def trigger_mlops_pipeline(
    background_tasks: BackgroundTasks,
    ops: Annotated[MlopsOpsService, Depends(get_mlops_ops_service)],
    current_user: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_writer_roles))],
) -> MlopsPipelineRunResponse:
    if not ops.config.pipeline_enabled:
        dashboard_mlops_pipeline_requests_total.labels(status="disabled").inc()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MLOps pipeline runner is disabled (set MLOPS_PIPELINE_ENABLED=true).",
        )

    run = ops.create_run(current_user)
    run_id = uuid.UUID(str(run.id))
    background_tasks.add_task(background_execute_run, run_id)
    dashboard_mlops_pipeline_requests_total.labels(status="accepted").inc()
    return ops._to_run_response(run)


@app.get("/mlops/pipeline/runs", response_model=list[MlopsPipelineRunResponse], tags=["mlops-ops"])
def list_mlops_pipeline_runs(
    ops: Annotated[MlopsOpsService, Depends(get_mlops_ops_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[MlopsPipelineRunResponse]:
    return ops.list_runs(limit=limit)


@app.get(
    "/mlops/pipeline/runs/{run_id}",
    response_model=MlopsPipelineRunResponse,
    tags=["mlops-ops"],
)
def get_mlops_pipeline_run(
    run_id: str,
    ops: Annotated[MlopsOpsService, Depends(get_mlops_ops_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
) -> MlopsPipelineRunResponse:
    response = ops.get_run_response(run_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run introuvable.")
    return response


@app.get(
    "/mlops/pipeline/runs/{run_id}/logs",
    response_model=MlopsPipelineRunLogsResponse,
    tags=["mlops-ops"],
)
def get_mlops_pipeline_run_logs(
    run_id: str,
    ops: Annotated[MlopsOpsService, Depends(get_mlops_ops_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
) -> MlopsPipelineRunLogsResponse:
    response = ops.get_run_logs(run_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run introuvable.")
    return response


# ---- Orchestration Center ----

@app.get("/mlops/orchestration/actions", response_model=list[MlopsActionDefinition], tags=["mlops-orchestration"])
def list_mlops_orchestration_actions(
    orchestration: Annotated[MlopsOrchestrationService, Depends(get_mlops_orchestration_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
) -> list[MlopsActionDefinition]:
    return orchestration.list_actions()


@app.post(
    "/mlops/orchestration/run",
    response_model=MlopsOrchestrationRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["mlops-orchestration"],
)
def trigger_mlops_orchestration_run(
    payload: MlopsOrchestrationRunRequest,
    background_tasks: BackgroundTasks,
    orchestration: Annotated[MlopsOrchestrationService, Depends(get_mlops_orchestration_service)],
    current_user: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_writer_roles))],
) -> MlopsOrchestrationRunResponse:
    try:
        run = orchestration.create_run(current_user, payload.action, payload.parameters)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    run_id = uuid.UUID(str(run.id))
    background_tasks.add_task(background_execute_orchestration_run, run_id)
    return orchestration._to_run_response(run)


@app.get("/mlops/orchestration/runs", response_model=list[MlopsOrchestrationRunResponse], tags=["mlops-orchestration"])
def list_mlops_orchestration_runs(
    orchestration: Annotated[MlopsOrchestrationService, Depends(get_mlops_orchestration_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[MlopsOrchestrationRunResponse]:
    return orchestration.list_runs(limit=limit)


@app.get(
    "/mlops/orchestration/runs/{run_id}",
    response_model=MlopsOrchestrationRunResponse,
    tags=["mlops-orchestration"],
)
def get_mlops_orchestration_run(
    run_id: str,
    orchestration: Annotated[MlopsOrchestrationService, Depends(get_mlops_orchestration_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
) -> MlopsOrchestrationRunResponse:
    response = orchestration.get_run_response(run_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run introuvable.")
    return response


@app.get(
    "/mlops/orchestration/runs/{run_id}/logs",
    response_model=MlopsOrchestrationRunLogsResponse,
    tags=["mlops-orchestration"],
)
def get_mlops_orchestration_run_logs(
    run_id: str,
    orchestration: Annotated[MlopsOrchestrationService, Depends(get_mlops_orchestration_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
) -> MlopsOrchestrationRunLogsResponse:
    response = orchestration.get_run_logs(run_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run introuvable.")
    return response


# ---- Drift detection (reads from api-bff-service which reads Redis) ---------

_BFF_BASE_URL = os.getenv("API_BFF_BASE_URL", "http://api-bff-service:8000").rstrip("/")
_DRIFT_MODEL_NAMES = ["congestion_5g", "sla_5g", "slice_type_5g"]
_EVALUATION_MODEL_NAMES = ["congestion_5g", "sla_5g", "slice_type_5g"]


@app.get("/mlops/drift", tags=["mlops"])
def get_mlops_drift(
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
) -> dict:
    """Return latest drift detection state for all Scenario B models.

    Reads from api-bff-service which proxies Redis aiops:drift:{model_name} hashes.
    Returns empty valid response if no drift data has been collected yet.
    """
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{_BFF_BASE_URL}/api/v1/drift/latest")
        if resp.status_code < 400:
            return resp.json()
    except Exception:  # noqa: BLE001
        pass
    # Graceful empty response — drift-monitor may not be running
    return {
        "models": {
            name: {"model_name": name, "status": "no_data"}
            for name in _DRIFT_MODEL_NAMES
        },
        "timestamp": None,
        "note": "drift-monitor not reachable or no data collected yet",
    }


@app.get("/mlops/drift/{model_name}", tags=["mlops"])
def get_mlops_drift_model(
    model_name: str,
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
) -> dict:
    """Return latest drift state for a single model."""
    if model_name not in _DRIFT_MODEL_NAMES:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown model '{model_name}'. Known: {_DRIFT_MODEL_NAMES}",
        )
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{_BFF_BASE_URL}/api/v1/drift/latest/{model_name}")
        if resp.status_code < 400:
            return resp.json()
    except Exception:  # noqa: BLE001
        pass
    return {"model_name": model_name, "status": "no_data"}


@app.get("/mlops/drift-events", tags=["mlops"])
def get_mlops_drift_events(
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    """Return recent drift alert events from events.drift stream."""
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(
                f"{_BFF_BASE_URL}/api/v1/drift/events", params={"limit": limit}
            )
        if resp.status_code < 400:
            return resp.json()
    except Exception:  # noqa: BLE001
        pass
    return {"events": [], "count": 0}


@app.get("/mlops/evaluation", tags=["mlops"])
def get_mlops_evaluation(
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
) -> dict:
    """Return latest online evaluation state for all Scenario B models."""
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{_BFF_BASE_URL}/api/v1/evaluation/latest")
        if resp.status_code < 400:
            return resp.json()
    except Exception:  # noqa: BLE001
        pass
    return {
        "models": {
            name: {"model_name": name, "status": "no_data", "pseudo_ground_truth_available": False}
            for name in _EVALUATION_MODEL_NAMES
        },
        "timestamp": None,
        "note": "online-evaluator not reachable or no data collected yet",
    }


@app.get("/mlops/evaluation/{model_name}", tags=["mlops"])
def get_mlops_evaluation_model(
    model_name: str,
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
) -> dict:
    """Return latest online evaluation state for one model."""
    if model_name not in _EVALUATION_MODEL_NAMES:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown model '{model_name}'. Known: {_EVALUATION_MODEL_NAMES}",
        )
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{_BFF_BASE_URL}/api/v1/evaluation/latest/{model_name}")
        if resp.status_code < 400:
            return resp.json()
    except Exception:  # noqa: BLE001
        pass
    return {"model_name": model_name, "status": "no_data", "pseudo_ground_truth_available": False}


# ---- MLOps pipeline config (read-only, for UI gating) ----------------------

@app.get(
    "/mlops/pipeline/config",
    response_model=MlopsPipelineConfigResponse,
    tags=["mlops-ops"],
)
def get_mlops_pipeline_config(
    ops: Annotated[MlopsOpsService, Depends(get_mlops_ops_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
) -> MlopsPipelineConfigResponse:
    enabled = ops.config.pipeline_enabled
    return MlopsPipelineConfigResponse(
        pipeline_enabled=enabled,
        message=(
            "Offline MLOps pipeline execution is enabled."
            if enabled
            else (
                "Offline MLOps pipeline execution is disabled by configuration. "
                "Set MLOPS_PIPELINE_ENABLED=true to enable it in Scenario B demo mode."
            )
        ),
    )


# ---- Agentic AI proxy routes (auth-protected) --------------------------------
# The browser must never call agent services directly. All agentic traffic from
# the browser must flow through these routes so that JWT/session validation is
# enforced before any agent call is forwarded.

agentic_roles = ("ADMIN", "NETWORK_OPERATOR", "NETWORK_MANAGER", "DATA_MLOPS_ENGINEER")


@app.get("/agentic/health", response_model=AgenticHealthResponse, tags=["agentic"])
def agentic_health(
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*agentic_roles))],
) -> AgenticHealthResponse:
    rca_status = "unknown"
    copilot_status = "unknown"
    detail: dict[str, Any] = {}

    with httpx.Client(timeout=3.0) as client:
        try:
            r = client.get(f"{_get_root_cause_url()}/health")
            rca_status = "ok" if r.status_code < 400 else "degraded"
            detail["root_cause_http"] = r.status_code
        except Exception as exc:
            rca_status = "unavailable"
            detail["root_cause_error"] = str(exc)

        try:
            r = client.get(f"{_get_copilot_url()}/health")
            copilot_status = "ok" if r.status_code < 400 else "degraded"
            detail["copilot_http"] = r.status_code
        except Exception as exc:
            copilot_status = "unavailable"
            detail["copilot_error"] = str(exc)

    return AgenticHealthResponse(
        root_cause=rca_status,
        copilot=copilot_status,
        detail=detail,
    )


@app.post("/agentic/root-cause/manual-scan", tags=["agentic"])
def agentic_rca_scan(
    body: dict[str, Any],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*agentic_roles))],
) -> Any:
    target_url = f"{_get_root_cause_url()}/internal/rca/manual-scan"
    try:
        with httpx.Client(timeout=90.0) as client:
            response = client.post(target_url, json=body)
    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "RCA_AGENT_UNAVAILABLE", "message": "Root-cause agent is not reachable."},
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"code": "RCA_AGENT_TIMEOUT", "message": "Root-cause agent timed out."},
        )

    if response.status_code >= 500:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "RCA_AGENT_ERROR", "message": "Root-cause agent returned an error."},
        )

    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get("content-type", "application/json"),
    )


@app.post("/agentic/copilot/query/text", tags=["agentic"])
def agentic_copilot_text(
    body: dict[str, Any],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*agentic_roles))],
) -> Any:
    target_url = f"{_get_copilot_url()}/copilot/query/text"
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(target_url, json=body)
    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "COPILOT_UNAVAILABLE", "message": "Copilot agent is not reachable."},
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"code": "COPILOT_TIMEOUT", "message": "Copilot agent timed out."},
        )

    if response.status_code >= 500:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "COPILOT_ERROR", "message": "Copilot agent returned an error."},
        )

    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get("content-type", "application/json"),
    )


@app.post("/agentic/copilot/query", tags=["agentic"])
async def agentic_copilot_stream(
    body: dict[str, Any],
    request: Request,
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*agentic_roles))],
) -> StreamingResponse:
    target_url = f"{_get_copilot_url()}/copilot/query"

    async def _stream():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", target_url, json=body) as upstream:
                    async for chunk in upstream.aiter_bytes():
                        if await request.is_disconnected():
                            return
                        yield chunk
        except httpx.ConnectError:
            yield b'event: error\ndata: {"code":"COPILOT_UNAVAILABLE","message":"Copilot agent is not reachable."}\n\n'
        except Exception as exc:
            yield f'event: error\ndata: {{"code":"PROXY_ERROR","message":"{exc}"}}\n\n'.encode()

    return StreamingResponse(_stream(), media_type="text/event-stream")


# ── Control tier proxy routes ──────────────────────────────────────────────────
# Proxy calls to policy-control service for the control/actions dashboard page.
# JWT auth is enforced here before forwarding. The policy-control service is
# internal-only (not exposed via Kong directly).

control_roles = ("ADMIN", "NETWORK_OPERATOR", "NETWORK_MANAGER")


def _get_policy_control_url() -> str:
    return os.getenv("POLICY_CONTROL_URL", "http://policy-control:7011").rstrip("/")


def _get_drift_monitor_url() -> str:
    return os.getenv("DRIFT_MONITOR_URL", "http://mlops-drift-monitor:8030").rstrip("/")


def _proxy_get(url: str) -> Response:
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(url)
            return Response(content=r.content, status_code=r.status_code,
                            media_type=r.headers.get("content-type", "application/json"))
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Control service unavailable.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


def _proxy_post(url: str, body: dict | None = None) -> Response:
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(url, json=body or {})
            return Response(content=r.content, status_code=r.status_code,
                            media_type=r.headers.get("content-type", "application/json"))
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Control service unavailable.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/controls/actions", tags=["controls"])
def list_control_actions(
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*control_roles))],
) -> Any:
    return _proxy_get(f"{_get_policy_control_url()}/actions")


@app.get("/controls/actions/{action_id}", tags=["controls"])
def get_control_action(
    action_id: str,
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*control_roles))],
) -> Any:
    return _proxy_get(f"{_get_policy_control_url()}/actions/{action_id}")


@app.get("/controls/actuations", tags=["controls"])
def list_control_actuations(
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*control_roles))],
) -> Any:
    return _proxy_get(f"{_get_policy_control_url()}/actuations")


@app.get("/controls/actuations/{action_id}", tags=["controls"])
def get_control_actuation(
    action_id: str,
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*control_roles))],
) -> Any:
    return _proxy_get(f"{_get_policy_control_url()}/actuations/{action_id}")


@app.post("/controls/actions/{action_id}/approve", tags=["controls"])
def approve_control_action(
    action_id: str,
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*control_roles))],
) -> Any:
    return _proxy_post(f"{_get_policy_control_url()}/actions/{action_id}/approve")


@app.post("/controls/actions/{action_id}/reject", tags=["controls"])
def reject_control_action(
    action_id: str,
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*control_roles))],
) -> Any:
    return _proxy_post(f"{_get_policy_control_url()}/actions/{action_id}/reject")


@app.post("/controls/actions/{action_id}/execute", tags=["controls"])
def execute_control_action(
    action_id: str,
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*control_roles))],
) -> Any:
    return _proxy_post(f"{_get_policy_control_url()}/actions/{action_id}/execute")


# ── Runtime service controls (Redis-backed flags) ─────────────────────────────

@app.get("/runtime/services", tags=["runtime"])
def list_runtime_services(
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*runtime_reader_roles))],
) -> dict[str, Any]:
    items = [_read_runtime_service_state(service_name) for service_name in runtime_controlled_services]
    return {"count": len(items), "items": items}


@app.get("/runtime/services/{service_name}", tags=["runtime"])
def get_runtime_service(
    service_name: str,
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*runtime_reader_roles))],
) -> dict[str, Any]:
    return _read_runtime_service_state(service_name)


@app.patch("/runtime/services/{service_name}", tags=["runtime"])
def patch_runtime_service(
    service_name: str,
    payload: RuntimeServicePatchRequest,
    current_user: Annotated[AuthenticatedPrincipal, Depends(get_current_user)],
) -> dict[str, Any]:
    if service_name not in runtime_controlled_services:
        raise HTTPException(status_code=404, detail=f"Unknown runtime service '{service_name}'.")
    if not _can_write_runtime(service_name, current_user):
        raise HTTPException(status_code=403, detail="Insufficient permissions to update runtime service flags.")

    if payload.mode is not None and payload.mode not in {"auto", "manual", "disabled"}:
        raise HTTPException(status_code=400, detail="mode must be one of: auto, manual, disabled")

    current = _read_runtime_service_state(service_name)
    next_enabled = payload.enabled if payload.enabled is not None else bool(current["enabled"])
    next_mode = payload.mode if payload.mode is not None else str(current["mode"])

    if next_mode == "disabled":
        next_enabled = False
    elif not next_enabled and payload.mode is None:
        next_mode = "disabled"

    reason = (payload.reason or "").strip() or str(current.get("reason") or "")
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    client = _runtime_redis_client()
    client.set(_runtime_key(service_name, "enabled"), "true" if next_enabled else "false")
    client.set(_runtime_key(service_name, "mode"), next_mode)
    client.set(_runtime_key(service_name, "updated_at"), now_iso)
    client.set(_runtime_key(service_name, "updated_by"), current_user.email)
    client.set(_runtime_key(service_name, "reason"), reason)
    return _read_runtime_service_state(service_name)


# ── Drift monitor proxy routes ─────────────────────────────────────────────────

@app.get("/controls/drift/status", tags=["controls"])
def drift_status_proxy(
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
) -> Any:
    return _proxy_get(f"{_get_drift_monitor_url()}/drift/status")


@app.get("/controls/drift/events", tags=["controls"])
def drift_events_proxy(
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
    limit: int = Query(default=20, ge=1, le=100),
) -> Any:
    return _proxy_get(f"{_get_drift_monitor_url()}/drift/events?limit={limit}")


@app.post("/controls/drift/trigger", tags=["controls"])
def drift_manual_trigger(
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_writer_roles))],
) -> Any:
    return _proxy_post(f"{_get_drift_monitor_url()}/drift/trigger")

