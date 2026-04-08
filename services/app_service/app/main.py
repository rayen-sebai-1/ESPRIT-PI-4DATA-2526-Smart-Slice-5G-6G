from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, Query
from sqlalchemy.orm import Session

from packages.neuroslice_common.config import get_settings
from packages.neuroslice_common.db import get_db
from packages.neuroslice_common.enums import RiskLevel, SliceType, UserRole
from packages.neuroslice_common.models import User
from packages.neuroslice_common.security import get_current_user, require_roles
from services.auth_service.app.main import (
    list_users as list_users_impl,
    login as login_impl,
    me as me_impl,
)
from services.auth_service.app.schemas import LoginRequest, TokenResponse, UserResponse
from services.dashboard_service.app.main import (
    manager_summary as manager_summary_impl,
    national_dashboard as national_dashboard_impl,
    region_dashboard as region_dashboard_impl,
)
from services.dashboard_service.app.schemas import (
    ManagerSummaryResponse,
    NationalDashboardResponse,
    RegionDashboardResponse,
)
from services.prediction_service.app.main import (
    get_prediction as get_prediction_impl,
    list_models as list_models_impl,
    list_predictions as list_predictions_impl,
    run_batch_predictions as run_batch_predictions_impl,
    run_prediction as run_prediction_impl,
)
from services.prediction_service.app.schemas import (
    ModelInfoResponse,
    PredictionListResponse,
    PredictionResponse,
    RunBatchRequest,
)
from services.session_service.app.main import (
    get_session as get_session_impl,
    list_sessions as list_sessions_impl,
)
from services.session_service.app.schemas import SessionListResponse, SessionSummary

settings = get_settings()

allowed_reader_roles = (UserRole.ADMIN, UserRole.NETWORK_OPERATOR, UserRole.NETWORK_MANAGER)
prediction_writer_roles = (UserRole.ADMIN, UserRole.NETWORK_OPERATOR)

app = FastAPI(
    title="NeuroSlice Tunisia - Unified App Service",
    version="1.0.0",
    description=(
        "Single-service demo backend for NeuroSlice Tunisia. "
        "It keeps the validated dashboard, monitoring and simple prediction flows."
    ),
)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.service_name,
        "mode": "single-service",
    }


@app.post("/auth/login", response_model=TokenResponse, tags=["auth"])
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    return login_impl(payload, db)


@app.get("/auth/me", response_model=UserResponse, tags=["auth"])
def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return me_impl(current_user)


@app.get("/users", response_model=list[UserResponse], tags=["users"])
def list_users(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> list[UserResponse]:
    return list_users_impl(current_user, db)


@app.get("/sessions", response_model=SessionListResponse, tags=["sessions"])
def list_sessions(
    current_user: Annotated[User, Depends(require_roles(*allowed_reader_roles))],
    db: Annotated[Session, Depends(get_db)],
    region: str | None = Query(default=None, description="Nom ou code region"),
    risk_level: RiskLevel | None = Query(default=None, alias="risk"),
    slice_type: SliceType | None = Query(default=None, alias="slice"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> SessionListResponse:
    return list_sessions_impl(current_user, db, region, risk_level, slice_type, page, page_size)


@app.get("/sessions/{session_id}", response_model=SessionSummary, tags=["sessions"])
def get_session(
    session_id: int,
    current_user: Annotated[User, Depends(require_roles(*allowed_reader_roles))],
    db: Annotated[Session, Depends(get_db)],
) -> SessionSummary:
    return get_session_impl(session_id, current_user, db)


@app.get("/models", response_model=list[ModelInfoResponse], tags=["predictions"])
def list_models(
    current_user: Annotated[User, Depends(require_roles(*allowed_reader_roles))],
) -> list[ModelInfoResponse]:
    return list_models_impl(current_user)


@app.get("/predictions", response_model=PredictionListResponse, tags=["predictions"])
def list_predictions(
    current_user: Annotated[User, Depends(require_roles(*allowed_reader_roles))],
    db: Annotated[Session, Depends(get_db)],
    region: str | None = Query(default=None),
    risk_level: RiskLevel | None = Query(default=None, alias="risk"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PredictionListResponse:
    return list_predictions_impl(current_user, db, region, risk_level, page, page_size)


@app.get("/predictions/{session_id}", response_model=PredictionResponse, tags=["predictions"])
def get_prediction(
    session_id: int,
    current_user: Annotated[User, Depends(require_roles(*allowed_reader_roles))],
    db: Annotated[Session, Depends(get_db)],
) -> PredictionResponse:
    return get_prediction_impl(session_id, current_user, db)


@app.post("/predictions/run/{session_id}", response_model=PredictionResponse, tags=["predictions"])
def run_prediction(
    session_id: int,
    current_user: Annotated[User, Depends(require_roles(*prediction_writer_roles))],
    db: Annotated[Session, Depends(get_db)],
) -> PredictionResponse:
    return run_prediction_impl(session_id, current_user, db)


@app.post("/predictions/run-batch", response_model=list[PredictionResponse], tags=["predictions"])
def run_batch_predictions(
    payload: RunBatchRequest,
    current_user: Annotated[User, Depends(require_roles(*prediction_writer_roles))],
    db: Annotated[Session, Depends(get_db)],
) -> list[PredictionResponse]:
    return run_batch_predictions_impl(payload, current_user, db)


@app.get("/dashboard/national", response_model=NationalDashboardResponse, tags=["dashboard"])
def national_dashboard(
    current_user: Annotated[User, Depends(require_roles(*allowed_reader_roles))],
    db: Annotated[Session, Depends(get_db)],
) -> NationalDashboardResponse:
    return national_dashboard_impl(current_user, db)


@app.get("/dashboard/region/{region_id}", response_model=RegionDashboardResponse, tags=["dashboard"])
def region_dashboard(
    region_id: int,
    current_user: Annotated[User, Depends(require_roles(*allowed_reader_roles))],
    db: Annotated[Session, Depends(get_db)],
) -> RegionDashboardResponse:
    return region_dashboard_impl(region_id, current_user, db)


@app.get("/dashboard/manager/summary", response_model=ManagerSummaryResponse, tags=["dashboard"])
def manager_summary(
    current_user: Annotated[User, Depends(require_roles(*allowed_reader_roles))],
    db: Annotated[Session, Depends(get_db)],
) -> ManagerSummaryResponse:
    return manager_summary_impl(current_user, db)
