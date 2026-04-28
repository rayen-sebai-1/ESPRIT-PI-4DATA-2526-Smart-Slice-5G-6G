from __future__ import annotations

from typing import Annotated

import uuid

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from db import check_database_connection, get_db
from mlops import MlopsService, get_mlops_service
from mlops_ops import MlopsOpsService, background_execute_run
from mlops_orchestration import MlopsOrchestrationService, background_execute_orchestration_run
from schemas import (
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

