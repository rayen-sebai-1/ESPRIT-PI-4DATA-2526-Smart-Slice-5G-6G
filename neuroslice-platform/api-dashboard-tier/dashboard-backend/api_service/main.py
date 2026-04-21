from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status

from common.data import (
    get_prediction,
    get_session,
    list_models_catalog,
    list_predictions,
    list_sessions,
    national_dashboard,
    region_dashboard,
    run_batch,
    run_prediction,
)
from common.schemas import (
    PredictionListResponse,
    ModelInfo,
    PredictionResponse,
    RunBatchRequest,
    SessionListResponse,
    SessionSummary,
    UserOut,
)
from common.security import require_roles

app = FastAPI(title="NeuroSlice Draft - API Service", version="1.0.0")
allowed_roles = ("ADMIN", "NETWORK_OPERATOR", "NETWORK_MANAGER")
writer_roles = ("ADMIN", "NETWORK_OPERATOR")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "api-service"}


@app.get("/dashboard/national", tags=["dashboard"])
def get_national_dashboard(_: Annotated[UserOut, Depends(require_roles(*allowed_roles))]):
    return national_dashboard()


@app.get("/dashboard/region/{region_id}", tags=["dashboard"])
def get_region_dashboard(
    region_id: int,
    _: Annotated[UserOut, Depends(require_roles(*allowed_roles))],
):
    response = region_dashboard(region_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region introuvable.")
    return response


@app.get("/sessions", response_model=SessionListResponse, tags=["sessions"])
def get_sessions(
    _: Annotated[UserOut, Depends(require_roles(*allowed_roles))],
    region: str | None = Query(default=None),
    risk: str | None = Query(default=None),
    slice: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> SessionListResponse:
    return list_sessions(region, risk, slice, page, page_size)


@app.get("/sessions/{session_id}", response_model=SessionSummary, tags=["sessions"])
def get_session_by_id(
    session_id: int,
    _: Annotated[UserOut, Depends(require_roles(*allowed_roles))],
) -> SessionSummary:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session introuvable.")
    return session


@app.get("/predictions", response_model=PredictionListResponse, tags=["predictions"])
def get_predictions(
    _: Annotated[UserOut, Depends(require_roles(*allowed_roles))],
    region: str | None = Query(default=None),
    risk: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PredictionListResponse:
    items, pagination = list_predictions(region, risk, page, page_size)
    return PredictionListResponse(items=items, pagination=pagination)


@app.get("/models", response_model=list[ModelInfo], tags=["predictions"])
def get_models_catalog(
    _: Annotated[UserOut, Depends(require_roles(*allowed_roles))],
) -> list[ModelInfo]:
    return list_models_catalog()


@app.get("/predictions/{session_id}", response_model=PredictionResponse, tags=["predictions"])
def get_prediction_by_session(
    session_id: int,
    _: Annotated[UserOut, Depends(require_roles(*allowed_roles))],
) -> PredictionResponse:
    prediction = get_prediction(session_id)
    if prediction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction introuvable.")
    return prediction


@app.post("/predictions/run/{session_id}", response_model=PredictionResponse, tags=["predictions"])
def rerun_prediction(
    session_id: int,
    _: Annotated[UserOut, Depends(require_roles(*writer_roles))],
) -> PredictionResponse:
    prediction = run_prediction(session_id)
    if prediction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session introuvable.")
    return prediction


@app.post("/predictions/run-batch", response_model=list[PredictionResponse], tags=["predictions"])
def rerun_batch(
    payload: RunBatchRequest,
    _: Annotated[UserOut, Depends(require_roles(*writer_roles))],
) -> list[PredictionResponse]:
    return run_batch(payload)
