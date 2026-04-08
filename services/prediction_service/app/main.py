from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from packages.neuroslice_common.config import get_settings
from packages.neuroslice_common.db import get_db
from packages.neuroslice_common.enums import RiskLevel, UserRole
from packages.neuroslice_common.models import NetworkSession, Prediction, Region, User
from packages.neuroslice_common.prediction_provider import get_prediction_provider
from packages.neuroslice_common.queries import latest_prediction_subquery
from packages.neuroslice_common.security import require_roles
from services.prediction_service.app.schemas import (
    ModelInfoResponse,
    PaginationMeta,
    PredictionListResponse,
    PredictionResponse,
    RegionLite,
    RunBatchRequest,
)

settings = get_settings()
provider = get_prediction_provider(settings)
reader_roles = (UserRole.ADMIN, UserRole.NETWORK_OPERATOR, UserRole.NETWORK_MANAGER)
writer_roles = (UserRole.ADMIN, UserRole.NETWORK_OPERATOR)

app = FastAPI(
    title="NeuroSlice Tunisia - Prediction Service",
    version="0.1.0",
)


def as_float(value: Decimal | None) -> float:
    return float(value) if value is not None else 0.0


def to_prediction_response(prediction: Prediction, session_obj: NetworkSession, region_obj: Region) -> PredictionResponse:
    return PredictionResponse(
        id=prediction.id,
        session_id=session_obj.id,
        session_code=session_obj.session_code,
        region=RegionLite(
            id=region_obj.id,
            code=region_obj.code,
            name=region_obj.name,
            ric_status=region_obj.ric_status,
            network_load=as_float(region_obj.network_load),
        ),
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


def build_prediction(*, db: Session, session_obj: NetworkSession, region_obj: Region) -> Prediction:
    result = provider.predict(session_obj, region_obj)
    prediction = Prediction(
        session_id=session_obj.id,
        sla_score=result.sla_score,
        congestion_score=result.congestion_score,
        anomaly_score=result.anomaly_score,
        risk_level=result.risk_level,
        predicted_slice_type=result.predicted_slice_type,
        slice_confidence=result.slice_confidence,
        recommended_action=result.recommended_action,
        model_source=result.model_source,
    )
    db.add(prediction)
    db.flush()
    return prediction


def fetch_session_with_region(db: Session, session_id: int) -> tuple[NetworkSession, Region] | None:
    row = db.execute(
        select(NetworkSession, Region)
        .join(Region, NetworkSession.region_id == Region.id)
        .where(NetworkSession.id == session_id)
    ).one_or_none()
    if row is None:
        return None
    return row[0], row[1]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/models", response_model=list[ModelInfoResponse], tags=["models"])
def list_models(_: Annotated[User, Depends(require_roles(*reader_roles))]) -> list[ModelInfoResponse]:
    return [ModelInfoResponse(**asdict(descriptor)) for descriptor in provider.catalog()]


@app.get("/predictions", response_model=PredictionListResponse, tags=["predictions"])
def list_predictions(
    _: Annotated[User, Depends(require_roles(*reader_roles))],
    db: Annotated[Session, Depends(get_db)],
    region: str | None = Query(default=None),
    risk_level: RiskLevel | None = Query(default=None, alias="risk"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PredictionListResponse:
    latest_sq = latest_prediction_subquery()
    latest_pred = aliased(Prediction)

    stmt = (
        select(NetworkSession, Region, latest_pred)
        .join(Region, NetworkSession.region_id == Region.id)
        .join(latest_sq, NetworkSession.id == latest_sq.c.session_id)
        .join(
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

    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.execute(
        stmt.order_by(latest_pred.predicted_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [to_prediction_response(prediction, session_obj, region_obj) for session_obj, region_obj, prediction in rows]

    return PredictionListResponse(
        items=items,
        pagination=PaginationMeta.from_values(page=page, page_size=page_size, total=total),
    )


@app.get("/predictions/{session_id}", response_model=PredictionResponse, tags=["predictions"])
def get_prediction(
    session_id: int,
    _: Annotated[User, Depends(require_roles(*reader_roles))],
    db: Annotated[Session, Depends(get_db)],
) -> PredictionResponse:
    latest_sq = latest_prediction_subquery()
    latest_pred = aliased(Prediction)
    row = db.execute(
        select(NetworkSession, Region, latest_pred)
        .join(Region, NetworkSession.region_id == Region.id)
        .join(latest_sq, NetworkSession.id == latest_sq.c.session_id)
        .join(
            latest_pred,
            and_(
                latest_pred.session_id == latest_sq.c.session_id,
                latest_pred.predicted_at == latest_sq.c.latest_predicted_at,
            ),
        )
        .where(NetworkSession.id == session_id)
    ).one_or_none()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prédiction introuvable pour cette session.")

    session_obj, region_obj, prediction = row
    return to_prediction_response(prediction, session_obj, region_obj)


@app.post("/predictions/run/{session_id}", response_model=PredictionResponse, tags=["predictions"])
def run_prediction(
    session_id: int,
    _: Annotated[User, Depends(require_roles(*writer_roles))],
    db: Annotated[Session, Depends(get_db)],
) -> PredictionResponse:
    row = fetch_session_with_region(db, session_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session introuvable.")

    session_obj, region_obj = row
    prediction = build_prediction(db=db, session_obj=session_obj, region_obj=region_obj)
    db.commit()
    db.refresh(prediction)
    return to_prediction_response(prediction, session_obj, region_obj)


@app.post("/predictions/run-batch", response_model=list[PredictionResponse], tags=["predictions"])
def run_batch_predictions(
    payload: RunBatchRequest,
    _: Annotated[User, Depends(require_roles(*writer_roles))],
    db: Annotated[Session, Depends(get_db)],
) -> list[PredictionResponse]:
    stmt = select(NetworkSession, Region).join(Region, NetworkSession.region_id == Region.id)
    if payload.region_id is not None:
        stmt = stmt.where(NetworkSession.region_id == payload.region_id)

    rows = db.execute(stmt.order_by(NetworkSession.timestamp.desc()).limit(payload.limit)).all()
    responses: list[PredictionResponse] = []
    for session_obj, region_obj in rows:
        prediction = build_prediction(db=db, session_obj=session_obj, region_obj=region_obj)
        responses.append(to_prediction_response(prediction, session_obj, region_obj))

    db.commit()
    return responses
