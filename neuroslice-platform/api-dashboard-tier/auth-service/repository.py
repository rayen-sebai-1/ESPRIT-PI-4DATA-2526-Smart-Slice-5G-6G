from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload

from models import AuditLog, Role, User, UserSession


class AuthRepository:
    def __init__(self, db: Session):
        self.db = db

    def _user_query(self) -> Select[tuple[User]]:
        return select(User).options(joinedload(User.role))

    def get_role_by_name(self, name: str) -> Role | None:
        statement = select(Role).where(Role.name == name)
        return self.db.scalar(statement)

    def get_user_by_email(self, email: str, *, include_deleted: bool = False) -> User | None:
        statement = self._user_query().where(User.email == email)
        if not include_deleted:
            statement = statement.where(User.deleted_at.is_(None))
        return self.db.scalar(statement)

    def get_user_by_id(self, user_id: int, *, include_deleted: bool = False) -> User | None:
        statement = self._user_query().where(User.id == user_id)
        if not include_deleted:
            statement = statement.where(User.deleted_at.is_(None))
        return self.db.scalar(statement)

    def list_users(self) -> list[User]:
        statement = self._user_query().where(User.deleted_at.is_(None)).order_by(User.id.asc())
        return list(self.db.scalars(statement).unique())

    def create_user(self, **values: object) -> User:
        user = User(**values)
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def create_session(self, **values: object) -> UserSession:
        session = UserSession(**values)
        self.db.add(session)
        self.db.flush()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: uuid.UUID) -> UserSession | None:
        statement = (
            select(UserSession)
            .options(joinedload(UserSession.user).joinedload(User.role))
            .where(UserSession.id == session_id)
        )
        return self.db.scalar(statement)

    def get_active_session(self, session_id: uuid.UUID) -> UserSession | None:
        now = datetime.now(UTC)
        statement = (
            select(UserSession)
            .options(joinedload(UserSession.user).joinedload(User.role))
            .where(UserSession.id == session_id)
            .where(UserSession.revoked_at.is_(None))
            .where(UserSession.expires_at > now)
        )
        return self.db.scalar(statement)

    def revoke_session(self, session: UserSession, reason: str) -> UserSession:
        if session.revoked_at is None:
            session.revoked_at = datetime.now(UTC)
            session.revoked_reason = reason
        return session

    def revoke_user_sessions(
        self,
        user_id: int,
        *,
        reason: str,
        exclude_session_id: uuid.UUID | None = None,
    ) -> int:
        now = datetime.now(UTC)
        statement = select(UserSession).where(UserSession.user_id == user_id).where(UserSession.revoked_at.is_(None))
        if exclude_session_id is not None:
            statement = statement.where(UserSession.id != exclude_session_id)

        sessions = list(self.db.scalars(statement))
        for session in sessions:
            session.revoked_at = now
            session.revoked_reason = reason
        return len(sessions)

    def create_audit_log(
        self,
        *,
        actor_user_id: int | None,
        target_user_id: int | None,
        action: str,
        status: str,
        ip_address: str | None,
        user_agent: str | None,
        metadata: dict[str, object] | None = None,
    ) -> AuditLog:
        record = AuditLog(
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            action=action,
            status=status,
            ip_address=ip_address,
            user_agent=user_agent,
            event_metadata=metadata or {},
        )
        self.db.add(record)
        self.db.flush()
        return record
