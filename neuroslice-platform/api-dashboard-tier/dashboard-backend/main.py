from __future__ import annotations

import os
from typing import Annotated, Any

import httpx
import uuid

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
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

dashboard_reader_roles = ("ADMIN", "NETWORK_OPERATOR", "NETWORK_MANAGER")
prediction_reader_roles = ("ADMIN", "NETWORK_OPERATOR", "NETWORK_MANAGER", "DATA_MLOPS_ENGINEER")
writer_roles = ("ADMIN", "NETWORK_OPERATOR")
mlops_reader_roles = ("ADMIN", "DATA_MLOPS_ENGINEER", "NETWORK_MANAGER")
mlops_writer_roles = ("ADMIN", "DATA_MLOPS_ENGINEER")


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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MLOps pipeline runner is disabled (set MLOPS_PIPELINE_ENABLED=true).",
        )

    run = ops.create_run(current_user)
    run_id = uuid.UUID(str(run.id))
    background_tasks.add_task(background_execute_run, run_id)
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
    return os.getenv("DRIFT_MONITOR_URL", "http://drift-monitor:8030").rstrip("/")


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


# ── Drift monitor proxy routes ─────────────────────────────────────────────────

@app.get("/controls/drift/status", tags=["controls"])
def drift_status_proxy(
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
) -> Any:
    return _proxy_get(f"{_get_drift_monitor_url()}/drift/status")


@app.get("/controls/drift/events", tags=["controls"])
def drift_events_proxy(
    limit: int = Query(default=20, ge=1, le=100),
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_reader_roles))],
) -> Any:
    return _proxy_get(f"{_get_drift_monitor_url()}/drift/events?limit={limit}")


@app.post("/controls/drift/trigger", tags=["controls"])
def drift_manual_trigger(
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles(*mlops_writer_roles))],
) -> Any:
    return _proxy_post(f"{_get_drift_monitor_url()}/drift/trigger")

