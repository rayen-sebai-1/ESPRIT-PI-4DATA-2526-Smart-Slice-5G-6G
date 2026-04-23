from __future__ import annotations

import os
import uuid
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from db import get_db
from models import AlertAcknowledgement, DashboardBookmark, DashboardPreference
from providers.base import DashboardDataProvider
from providers.bff import BffDashboardProvider
from providers.temporary_mock import TemporaryMockProvider
from repository import DashboardRepository
from schemas import (
    AlertAcknowledgementResponse,
    AuthenticatedPrincipal,
    DashboardBookmarkPayload,
    DashboardBookmarkResponse,
    DashboardPreferencesPayload,
    DashboardPreferencesResponse,
)
from security import decode_access_token, get_bearer_token, get_dashboard_provider_name, require_access_token


@lru_cache(maxsize=1)
def get_dashboard_provider() -> DashboardDataProvider:
    provider_name = get_dashboard_provider_name()
    if provider_name == "bff":
        base_url = os.getenv("API_BFF_BASE_URL")
        if not base_url:
            raise RuntimeError("API_BFF_BASE_URL must be configured when DASHBOARD_DATA_PROVIDER=bff.")
        return BffDashboardProvider(base_url)
    return TemporaryMockProvider()


class DashboardService:
    def __init__(self, db: Session, provider: DashboardDataProvider):
        self.db = db
        self.repo = DashboardRepository(db)
        self.provider = provider

    def get_current_principal(self, access_token: str | None) -> AuthenticatedPrincipal:
        token = require_access_token(access_token)
        try:
            payload = decode_access_token(token)
            session_id = uuid.UUID(str(payload["sid"]))
            user_id = int(str(payload["sub"]))
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide.") from exc

        session = self.repo.get_active_auth_session(session_id)
        if (
            session is None
            or session.user.deleted_at is not None
            or not session.user.is_active
            or session.user.id != user_id
        ):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalide.")

        return AuthenticatedPrincipal(
            id=session.user.id,
            session_id=str(session.id),
            full_name=session.user.full_name,
            email=session.user.email,
            role=session.user.role.name,
            is_active=session.user.is_active,
        )

    def get_preferences(self, user: AuthenticatedPrincipal) -> DashboardPreferencesResponse:
        record = self.repo.get_preferences(user.id, scope="me")
        return DashboardPreferencesResponse(
            scope="me",
            preferences=record.preferences if record is not None else {},
            updated_at=record.updated_at if record is not None else None,
        )

    def update_preferences(
        self,
        user: AuthenticatedPrincipal,
        payload: DashboardPreferencesPayload,
    ) -> DashboardPreferencesResponse:
        record = self.repo.upsert_preferences(user.id, scope="me", preferences=payload.preferences)
        self.db.commit()
        return self._preferences_response(record)

    def list_bookmarks(self, user: AuthenticatedPrincipal) -> list[DashboardBookmarkResponse]:
        return [self._bookmark_response(bookmark) for bookmark in self.repo.list_bookmarks(user.id)]

    def save_bookmark(
        self,
        user: AuthenticatedPrincipal,
        payload: DashboardBookmarkPayload,
    ) -> DashboardBookmarkResponse:
        bookmark = self.repo.save_bookmark(
            user.id,
            resource_key=payload.resource_key,
            resource_type=payload.resource_type,
            title=payload.title,
            payload=payload.payload,
        )
        self.db.commit()
        return self._bookmark_response(bookmark)

    def delete_bookmark(self, user: AuthenticatedPrincipal, bookmark_id: int) -> None:
        deleted = self.repo.delete_bookmark(user.id, bookmark_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark introuvable.")
        self.db.commit()

    def acknowledge_alert(
        self,
        user: AuthenticatedPrincipal,
        *,
        alert_key: str,
        note: str | None,
    ) -> AlertAcknowledgementResponse:
        record = self.repo.acknowledge_alert(user.id, alert_key=alert_key, note=note)
        self.db.commit()
        return self._ack_response(record)

    @staticmethod
    def _preferences_response(record: DashboardPreference) -> DashboardPreferencesResponse:
        return DashboardPreferencesResponse(
            scope=record.scope,
            preferences=record.preferences,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _bookmark_response(record: DashboardBookmark) -> DashboardBookmarkResponse:
        return DashboardBookmarkResponse(
            id=record.id,
            resource_key=record.resource_key,
            resource_type=record.resource_type,
            title=record.title,
            payload=record.payload,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _ack_response(record: AlertAcknowledgement) -> AlertAcknowledgementResponse:
        return AlertAcknowledgementResponse(
            id=record.id,
            alert_key=record.alert_key,
            note=record.note,
            acknowledged_at=record.acknowledged_at,
        )


def get_dashboard_service(db: Annotated[Session, Depends(get_db)]) -> DashboardService:
    return DashboardService(db, get_dashboard_provider())


def get_current_user(
    access_token: Annotated[str | None, Depends(get_bearer_token)],
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
) -> AuthenticatedPrincipal:
    return dashboard_service.get_current_principal(access_token)


def require_roles(*roles: str):
    def checker(current_user: Annotated[AuthenticatedPrincipal, Depends(get_current_user)]) -> AuthenticatedPrincipal:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acces refuse.")
        return current_user

    return checker
