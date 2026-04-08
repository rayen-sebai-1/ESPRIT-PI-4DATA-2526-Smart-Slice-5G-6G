from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import and_, case, desc, func, select
from sqlalchemy.orm import Session, aliased

from packages.neuroslice_common.config import get_settings
from packages.neuroslice_common.db import get_db
from packages.neuroslice_common.enums import RiskLevel, UserRole
from packages.neuroslice_common.models import DashboardSnapshot, NetworkSession, Prediction, Region, User
from packages.neuroslice_common.queries import latest_prediction_subquery
from packages.neuroslice_common.security import require_roles
from services.dashboard_service.app.schemas import (
    ManagerSummaryResponse,
    NationalDashboardResponse,
    NationalOverview,
    RegionComparison,
    RegionDashboardResponse,
    SliceDistributionPoint,
    TrendPoint,
)

settings = get_settings()
allowed_roles = (UserRole.ADMIN, UserRole.NETWORK_OPERATOR, UserRole.NETWORK_MANAGER)

app = FastAPI(
    title="NeuroSlice Tunisia - Dashboard Service",
    version="0.1.0",
)


def as_float(value: Decimal | None) -> float:
    return round(float(value), 2) if value is not None else 0.0


def load_region_comparison_rows(db: Session) -> list[RegionComparison]:
    latest_sq = latest_prediction_subquery()
    latest_pred = aliased(Prediction)
    high_risk_case = case((latest_pred.risk_level.in_([RiskLevel.HIGH, RiskLevel.CRITICAL]), 1), else_=0)
    anomaly_case = case((latest_pred.anomaly_score >= 0.65, 1), else_=0)

    stmt = (
        select(
            Region.id,
            Region.code,
            Region.name,
            Region.ric_status,
            Region.network_load,
            Region.gnodeb_count,
            func.count(NetworkSession.id).label("sessions_count"),
            func.coalesce(func.avg(NetworkSession.latency_ms), 0).label("avg_latency_ms"),
            func.coalesce(func.avg(NetworkSession.packet_loss), 0).label("avg_packet_loss"),
            func.coalesce(func.avg(latest_pred.sla_score) * 100, 0).label("sla_percent"),
            func.coalesce(func.avg(latest_pred.congestion_score) * 100, 0).label("congestion_rate"),
            func.coalesce(func.sum(high_risk_case), 0).label("high_risk_sessions_count"),
            func.coalesce(func.sum(anomaly_case), 0).label("anomalies_count"),
        )
        .select_from(Region)
        .outerjoin(NetworkSession, NetworkSession.region_id == Region.id)
        .outerjoin(latest_sq, NetworkSession.id == latest_sq.c.session_id)
        .outerjoin(
            latest_pred,
            and_(
                latest_pred.session_id == latest_sq.c.session_id,
                latest_pred.predicted_at == latest_sq.c.latest_predicted_at,
            ),
        )
        .group_by(Region.id, Region.code, Region.name, Region.ric_status, Region.network_load, Region.gnodeb_count)
        .order_by(desc(Region.network_load), Region.name.asc())
    )
    rows = db.execute(stmt).all()
    return [
        RegionComparison(
            region_id=row.id,
            code=row.code,
            name=row.name,
            ric_status=row.ric_status,
            network_load=as_float(row.network_load),
            gnodeb_count=row.gnodeb_count,
            sessions_count=int(row.sessions_count or 0),
            sla_percent=as_float(row.sla_percent),
            avg_latency_ms=as_float(row.avg_latency_ms),
            avg_packet_loss=as_float(row.avg_packet_loss),
            congestion_rate=as_float(row.congestion_rate),
            high_risk_sessions_count=int(row.high_risk_sessions_count or 0),
            anomalies_count=int(row.anomalies_count or 0),
        )
        for row in rows
    ]


def load_national_overview(db: Session) -> NationalOverview:
    latest_sq = latest_prediction_subquery()
    latest_pred = aliased(Prediction)
    high_risk_case = case((latest_pred.risk_level.in_([RiskLevel.HIGH, RiskLevel.CRITICAL]), 1), else_=0)
    anomaly_case = case((latest_pred.anomaly_score >= 0.65, 1), else_=0)

    stmt = (
        select(
            func.count(NetworkSession.id).label("sessions_count"),
            func.coalesce(func.avg(NetworkSession.latency_ms), 0).label("avg_latency_ms"),
            func.coalesce(func.avg(latest_pred.sla_score) * 100, 0).label("sla_percent"),
            func.coalesce(func.avg(latest_pred.congestion_score) * 100, 0).label("congestion_rate"),
            func.coalesce(func.sum(high_risk_case), 0).label("active_alerts_count"),
            func.coalesce(func.sum(anomaly_case), 0).label("anomalies_count"),
        )
        .select_from(NetworkSession)
        .outerjoin(latest_sq, NetworkSession.id == latest_sq.c.session_id)
        .outerjoin(
            latest_pred,
            and_(
                latest_pred.session_id == latest_sq.c.session_id,
                latest_pred.predicted_at == latest_sq.c.latest_predicted_at,
            ),
        )
    )
    row = db.execute(stmt).one()
    generated_at = db.scalar(
        select(DashboardSnapshot.generated_at)
        .where(DashboardSnapshot.region_id.is_(None))
        .order_by(DashboardSnapshot.generated_at.desc())
        .limit(1)
    )

    return NationalOverview(
        sla_national_percent=as_float(row.sla_percent),
        avg_latency_ms=as_float(row.avg_latency_ms),
        congestion_rate=as_float(row.congestion_rate),
        active_alerts_count=int(row.active_alerts_count or 0),
        sessions_count=int(row.sessions_count or 0),
        anomalies_count=int(row.anomalies_count or 0),
        generated_at=generated_at,
    )


def load_trend(db: Session, region_id: int | None) -> list[TrendPoint]:
    where_clause = DashboardSnapshot.region_id == region_id if region_id is not None else DashboardSnapshot.region_id.is_(None)
    snapshots = list(
        reversed(
            db.scalars(
                select(DashboardSnapshot)
                .where(where_clause)
                .order_by(DashboardSnapshot.generated_at.desc())
                .limit(7)
            ).all()
        )
    )
    return [
        TrendPoint(
            label=snapshot.generated_at.strftime("%Y-%m-%d"),
            generated_at=snapshot.generated_at,
            sla_percent=as_float(snapshot.sla_percent),
            congestion_rate=as_float(snapshot.congestion_rate),
            active_alerts_count=snapshot.active_alerts_count,
            anomalies_count=snapshot.anomalies_count,
            total_sessions=snapshot.total_sessions,
        )
        for snapshot in snapshots
    ]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/dashboard/national", response_model=NationalDashboardResponse, tags=["dashboard"])
def national_dashboard(
    _: Annotated[User, Depends(require_roles(*allowed_roles))],
    db: Annotated[Session, Depends(get_db)],
) -> NationalDashboardResponse:
    return NationalDashboardResponse(
        overview=load_national_overview(db),
        regions=load_region_comparison_rows(db),
    )


@app.get("/dashboard/region/{region_id}", response_model=RegionDashboardResponse, tags=["dashboard"])
def region_dashboard(
    region_id: int,
    _: Annotated[User, Depends(require_roles(*allowed_roles))],
    db: Annotated[Session, Depends(get_db)],
) -> RegionDashboardResponse:
    region_rows = load_region_comparison_rows(db)
    region_summary = next((row for row in region_rows if row.region_id == region_id), None)
    if region_summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Région introuvable.")

    slice_stmt = (
        select(NetworkSession.slice_type, func.count(NetworkSession.id))
        .where(NetworkSession.region_id == region_id)
        .group_by(NetworkSession.slice_type)
        .order_by(func.count(NetworkSession.id).desc())
    )
    distribution = [
        SliceDistributionPoint(slice_type=slice_type.value, sessions_count=count)
        for slice_type, count in db.execute(slice_stmt).all()
    ]

    return RegionDashboardResponse(
        region=region_summary,
        gnodeb_count=region_summary.gnodeb_count,
        packet_loss_avg=region_summary.avg_packet_loss,
        slice_distribution=distribution,
        trend=load_trend(db, region_id),
    )


@app.get("/dashboard/manager/summary", response_model=ManagerSummaryResponse, tags=["dashboard"])
def manager_summary(
    _: Annotated[User, Depends(require_roles(*allowed_roles))],
    db: Annotated[Session, Depends(get_db)],
) -> ManagerSummaryResponse:
    national = load_national_overview(db)
    trend = load_trend(db, None)
    regions = load_region_comparison_rows(db)
    return ManagerSummaryResponse(
        national_overview=national,
        regions_comparison=regions,
        sla_trend=trend,
        congestion_trend=trend,
    )
