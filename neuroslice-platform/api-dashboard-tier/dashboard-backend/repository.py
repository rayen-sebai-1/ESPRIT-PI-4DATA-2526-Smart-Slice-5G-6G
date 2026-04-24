from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from models import (
    AlertAcknowledgement,
    AuthUser,
    AuthUserSession,
    DashboardBookmark,
    DashboardPreference,
)


class DashboardRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_active_auth_session(self, session_id: uuid.UUID) -> AuthUserSession | None:
        now = datetime.now(UTC)
        statement = (
            select(AuthUserSession)
            .options(joinedload(AuthUserSession.user).joinedload(AuthUser.role))
            .where(AuthUserSession.id == session_id)
            .where(AuthUserSession.revoked_at.is_(None))
            .where(AuthUserSession.expires_at > now)
        )
        return self.db.scalar(statement)

    def get_preferences(self, user_id: int, *, scope: str = "me") -> DashboardPreference | None:
        statement = (
            select(DashboardPreference)
            .where(DashboardPreference.user_id == user_id)
            .where(DashboardPreference.scope == scope)
        )
        return self.db.scalar(statement)

    def upsert_preferences(self, user_id: int, *, scope: str, preferences: dict[str, object]) -> DashboardPreference:
        record = self.get_preferences(user_id, scope=scope)
        if record is None:
            record = DashboardPreference(user_id=user_id, scope=scope, preferences=preferences)
            self.db.add(record)
        else:
            record.preferences = preferences
        self.db.flush()
        return record

    def list_bookmarks(self, user_id: int) -> list[DashboardBookmark]:
        statement = (
            select(DashboardBookmark)
            .where(DashboardBookmark.user_id == user_id)
            .order_by(DashboardBookmark.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def get_bookmark_by_resource_key(self, user_id: int, resource_key: str) -> DashboardBookmark | None:
        statement = (
            select(DashboardBookmark)
            .where(DashboardBookmark.user_id == user_id)
            .where(DashboardBookmark.resource_key == resource_key)
        )
        return self.db.scalar(statement)

    def save_bookmark(
        self,
        user_id: int,
        *,
        resource_key: str,
        resource_type: str,
        title: str,
        payload: dict[str, object],
    ) -> DashboardBookmark:
        bookmark = self.get_bookmark_by_resource_key(user_id, resource_key)
        if bookmark is None:
            bookmark = DashboardBookmark(
                user_id=user_id,
                resource_key=resource_key,
                resource_type=resource_type,
                title=title,
                payload=payload,
            )
            self.db.add(bookmark)
        else:
            bookmark.resource_type = resource_type
            bookmark.title = title
            bookmark.payload = payload
        self.db.flush()
        return bookmark

    def delete_bookmark(self, user_id: int, bookmark_id: int) -> bool:
        statement = (
            select(DashboardBookmark)
            .where(DashboardBookmark.user_id == user_id)
            .where(DashboardBookmark.id == bookmark_id)
        )
        bookmark = self.db.scalar(statement)
        if bookmark is None:
            return False
        self.db.delete(bookmark)
        self.db.flush()
        return True

    def acknowledge_alert(self, user_id: int, *, alert_key: str, note: str | None) -> AlertAcknowledgement:
        statement = (
            select(AlertAcknowledgement)
            .where(AlertAcknowledgement.user_id == user_id)
            .where(AlertAcknowledgement.alert_key == alert_key)
        )
        record = self.db.scalar(statement)
        if record is None:
            record = AlertAcknowledgement(user_id=user_id, alert_key=alert_key, note=note)
            self.db.add(record)
        else:
            record.note = note
            record.acknowledged_at = datetime.now(UTC)
        self.db.flush()
        return record
