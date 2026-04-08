from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from packages.neuroslice_common.config import get_settings
from packages.neuroslice_common.db import get_db
from packages.neuroslice_common.enums import RiskLevel, SliceType, UserRole
from packages.neuroslice_common.models import NetworkSession, Prediction, Region, User
from packages.neuroslice_common.queries import latest_prediction_subquery
from packages.neuroslice_common.security import require_roles
from services.session_service.app.schemas import (
    PaginationMeta,
    PredictionSummary,
    RegionSummary,
    SessionListResponse,
    SessionSummary,
)

settings = get_settings()
allowed_reader_roles = (UserRole.ADMIN, UserRole.NETWORK_OPERATOR, UserRole.NETWORK_MANAGER)

app = FastAPI(
    title="NeuroSlice Tunisia - Session Service",
    version="0.1.0",
)


def as_float(value: Decimal | None) -> float:
    return float(value) if value is not None else 0.0


def to_prediction_summary(prediction: Prediction | None) -> PredictionSummary | None:
    if prediction is None:
        return None
    return PredictionSummary(
        id=prediction.id,
        sla_score=as_float(prediction.sla_score),
        congestion_score=as_float(prediction.congestion_score),
        anomaly_score=as_float(prediction.anomaly_score),
        risk_level=prediction.risk_level,
        predicted_slice_type=prediction.predicted_slice_type,
        slice_confidence=as_float(prediction.slice_confidence),
        recommended_action=prediction.recommended_action,
        model_source=prediction.model_source,
        predicted_at=prediction.predicted_at,
    )


def to_session_summary(session: NetworkSession, region: Region, prediction: Prediction | None) -> SessionSummary:
    return SessionSummary(
        id=session.id,
        session_code=session.session_code,
        region=RegionSummary(
            id=region.id,
            code=region.code,
            name=region.name,
            ric_status=region.ric_status,
            network_load=as_float(region.network_load),
            gnodeb_count=region.gnodeb_count,
        ),
        slice_type=session.slice_type,
        latency_ms=as_float(session.latency_ms),
        packet_loss=as_float(session.packet_loss),
        throughput_mbps=as_float(session.throughput_mbps),
        timestamp=session.timestamp,
        prediction=to_prediction_summary(prediction),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/sessions", response_model=SessionListResponse, tags=["sessions"])
def list_sessions(
    _: Annotated[User, Depends(require_roles(*allowed_reader_roles))],
    db: Annotated[Session, Depends(get_db)],
    region: str | None = Query(default=None, description="Nom ou code région"),
    risk_level: RiskLevel | None = Query(default=None, alias="risk"),
    slice_type: SliceType | None = Query(default=None, alias="slice"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> SessionListResponse:
    latest_sq = latest_prediction_subquery()
    latest_pred = aliased(Prediction)

    stmt = (
        select(NetworkSession, Region, latest_pred)
        .join(Region, NetworkSession.region_id == Region.id)
        .outerjoin(latest_sq, NetworkSession.id == latest_sq.c.session_id)
        .outerjoin(
            latest_pred,
            and_(
                latest_pred.session_id == latest_sq.c.session_id,
                latest_pred.predicted_at == latest_sq.c.latest_predicted_at,
            ),
        )
    )

    if region:
        pattern = f"%{region}%"
        stmt = stmt.where(or_(Region.name.ilike(pattern), Region.code.ilike(pattern)))
    if risk_level is not None:
        stmt = stmt.where(latest_pred.risk_level == risk_level)
    if slice_type is not None:
        stmt = stmt.where(NetworkSession.slice_type == slice_type)

    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.execute(
        stmt.order_by(NetworkSession.timestamp.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    items = [to_session_summary(session_obj, region_obj, prediction) for session_obj, region_obj, prediction in rows]
    return SessionListResponse(
        items=items,
        pagination=PaginationMeta.from_values(page=page, page_size=page_size, total=total),
    )


@app.get("/sessions/{session_id}", response_model=SessionSummary, tags=["sessions"])
def get_session(
    session_id: int,
    _: Annotated[User, Depends(require_roles(*allowed_reader_roles))],
    db: Annotated[Session, Depends(get_db)],
) -> SessionSummary:
    latest_sq = latest_prediction_subquery()
    latest_pred = aliased(Prediction)

    stmt = (
        select(NetworkSession, Region, latest_pred)
        .join(Region, NetworkSession.region_id == Region.id)
        .outerjoin(latest_sq, NetworkSession.id == latest_sq.c.session_id)
        .outerjoin(
            latest_pred,
            and_(
                latest_pred.session_id == latest_sq.c.session_id,
                latest_pred.predicted_at == latest_sq.c.latest_predicted_at,
            ),
        )
        .where(NetworkSession.id == session_id)
    )
    row = db.execute(stmt).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session introuvable.")

    session_obj, region_obj, prediction = row
    return to_session_summary(session_obj, region_obj, prediction)
