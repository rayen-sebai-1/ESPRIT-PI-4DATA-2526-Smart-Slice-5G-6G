from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status

from db import check_database_connection
from schemas import (
    AlertAcknowledgePayload,
    AlertAcknowledgementResponse,
    AuthenticatedPrincipal,
    DashboardBookmarkPayload,
    DashboardBookmarkResponse,
    DashboardPreferencesPayload,
    DashboardPreferencesResponse,
    ModelInfo,
    PredictionListResponse,
    PredictionResponse,
    RunBatchRequest,
    SessionListResponse,
    SessionSummary,
)
from service import DashboardService, get_current_user, get_dashboard_provider, get_dashboard_service, require_roles

app = FastAPI(title="NeuroSlice Dashboard Backend", version="2.0.0")

dashboard_reader_roles = ("ADMIN", "NETWORK_OPERATOR", "NETWORK_MANAGER")
prediction_reader_roles = ("ADMIN", "NETWORK_OPERATOR", "NETWORK_MANAGER", "DATA_MLOPS_ENGINEER")
writer_roles = ("ADMIN", "NETWORK_OPERATOR")


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
