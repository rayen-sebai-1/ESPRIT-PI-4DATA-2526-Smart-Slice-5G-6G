from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from db import get_db
from models import User
from repository import AuthRepository
from schemas import (
    AdminCreateUserPayload,
    AdminUpdateUserPayload,
    AuthenticatedPrincipal,
    UserOut,
)
from security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_bearer_token,
    hash_password,
    hash_token,
    require_access_token,
    verify_password,
)

ASSIGNABLE_ROLES = {"NETWORK_OPERATOR", "NETWORK_MANAGER", "DATA_MLOPS_ENGINEER"}


@dataclass(slots=True)
class ClientContext:
    ip_address: str | None
    user_agent: str | None


@dataclass(slots=True)
class AuthSessionBundle:
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_expires_at: datetime
    session_id: str
    user: UserOut


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AuthRepository(db)

    def _serialize_user(self, user: User) -> UserOut:
        if user.role is None:
            raise RuntimeError("User role relationship must be loaded.")
        return UserOut(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            role=user.role.name,
            is_active=user.is_active,
        )

    def _audit(
        self,
        *,
        action: str,
        status_value: str,
        client: ClientContext,
        actor_user_id: int | None = None,
        target_user_id: int | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.repo.create_audit_log(
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            action=action,
            status=status_value,
            ip_address=client.ip_address,
            user_agent=client.user_agent,
            metadata=metadata,
        )

    def _issue_session_bundle(self, user: User, *, client: ClientContext, session_id: uuid.UUID | None = None) -> AuthSessionBundle:
        refresh_expires_at = datetime.now(UTC)
        if session_id is None:
            session = self.repo.create_session(
                user_id=user.id,
                refresh_token_hash="pending",
                expires_at=refresh_expires_at,
                last_used_at=datetime.now(UTC),
                ip_address=client.ip_address,
                user_agent=client.user_agent,
            )
        else:
            session = self.repo.get_active_session(session_id)
            if session is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalide.")
            session.last_used_at = datetime.now(UTC)
            session.ip_address = client.ip_address or session.ip_address
            session.user_agent = client.user_agent or session.user_agent

        access_token, expires_in = create_access_token(
            user_id=user.id,
            session_id=session.id,
            role=user.role.name,
        )
        refresh_token, refresh_expires_at = create_refresh_token(
            user_id=user.id,
            session_id=session.id,
            role=user.role.name,
        )
        session.refresh_token_hash = hash_token(refresh_token)
        session.expires_at = refresh_expires_at
        session.last_used_at = datetime.now(UTC)

        return AuthSessionBundle(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            refresh_expires_at=refresh_expires_at,
            session_id=str(session.id),
            user=self._serialize_user(user),
        )

    def authenticate_user(self, email: str, password: str, *, client: ClientContext) -> AuthSessionBundle:
        normalized_email = email.strip().lower()
        user = self.repo.get_user_by_email(normalized_email, include_deleted=True)
        if (
            user is None
            or user.deleted_at is not None
            or not user.is_active
            or not verify_password(password, user.password_hash)
        ):
            self._audit(
                action="LOGIN",
                status_value="FAILURE",
                client=client,
                metadata={"email": normalized_email},
            )
            self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou mot de passe invalide.",
            )

        bundle = self._issue_session_bundle(user, client=client)
        self._audit(
            action="LOGIN",
            status_value="SUCCESS",
            client=client,
            actor_user_id=user.id,
            target_user_id=user.id,
            metadata={"session_id": bundle.session_id},
        )
        self.db.commit()
        return bundle

    def refresh_session(self, refresh_token: str | None, *, client: ClientContext) -> AuthSessionBundle:
        if not refresh_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token manquant.")

        try:
            payload = decode_token(refresh_token, expected_type="refresh")
            session_id = uuid.UUID(str(payload["sid"]))
            user_id = int(str(payload["sub"]))
        except (InvalidTokenError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalide.") from exc

        session = self.repo.get_active_session(session_id)
        if (
            session is None
            or session.user.deleted_at is not None
            or not session.user.is_active
            or session.user.id != user_id
        ):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalide.")

        expected_hash = hash_token(refresh_token)
        if session.refresh_token_hash != expected_hash:
            self.repo.revoke_session(session, "refresh_token_mismatch")
            self._audit(
                action="REFRESH",
                status_value="FAILURE",
                client=client,
                actor_user_id=session.user_id,
                target_user_id=session.user_id,
                metadata={"session_id": str(session.id)},
            )
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalide.")

        bundle = self._issue_session_bundle(session.user, client=client, session_id=session.id)
        self._audit(
            action="REFRESH",
            status_value="SUCCESS",
            client=client,
            actor_user_id=session.user_id,
            target_user_id=session.user_id,
            metadata={"session_id": str(session.id)},
        )
        self.db.commit()
        return bundle

    def get_current_principal(self, access_token: str | None) -> AuthenticatedPrincipal:
        token = require_access_token(access_token)

        try:
            payload = decode_token(token, expected_type="access")
            session_id = uuid.UUID(str(payload["sid"]))
            user_id = int(str(payload["sub"]))
        except (InvalidTokenError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide.") from exc

        session = self.repo.get_active_session(session_id)
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

    def list_users(self) -> list[UserOut]:
        return [self._serialize_user(user) for user in self.repo.list_users()]

    def create_user(
        self,
        actor: AuthenticatedPrincipal,
        payload: AdminCreateUserPayload,
        *,
        client: ClientContext,
    ) -> UserOut:
        role_name = payload.role
        full_name = payload.full_name.strip()
        email = payload.email.strip().lower()

        if not full_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le nom complet est obligatoire.")
        if role_name not in ASSIGNABLE_ROLES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role invalide.")
        if self.repo.get_user_by_email(email, include_deleted=True) is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Un compte existe deja avec cet email.")

        role = self.repo.get_role_by_name(role_name)
        if role is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Role introuvable.")

        user = self.repo.create_user(
            full_name=full_name,
            email=email,
            password_hash=hash_password(payload.password),
            role_id=role.id,
            is_active=True,
            password_changed_at=datetime.now(UTC),
        )
        self._audit(
            action="USER_CREATE",
            status_value="SUCCESS",
            client=client,
            actor_user_id=actor.id,
            target_user_id=user.id,
            metadata={"email": email, "role": role_name},
        )
        self.db.commit()
        return self._serialize_user(user)

    def update_user(
        self,
        actor: AuthenticatedPrincipal,
        user_id: int,
        payload: AdminUpdateUserPayload,
        *,
        client: ClientContext,
    ) -> UserOut:
        user = self.repo.get_user_by_id(user_id, include_deleted=True)
        if user is None or user.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable.")

        if user.role.name == "ADMIN" and payload.role is not None and payload.role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le role d'un administrateur ne peut pas etre modifie.",
            )

        events: list[tuple[str, dict[str, object]]] = []

        if payload.full_name is not None:
            full_name = payload.full_name.strip()
            if not full_name:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le nom complet est obligatoire.")
            user.full_name = full_name
            events.append(("USER_UPDATE", {"field": "full_name"}))

        if payload.role is not None:
            if payload.role not in ASSIGNABLE_ROLES:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role invalide.")
            role = self.repo.get_role_by_name(payload.role)
            if role is None:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Role introuvable.")
            if user.role_id != role.id:
                previous_role = user.role.name
                user.role_id = role.id
                self.db.flush()
                user = self.repo.get_user_by_id(user_id, include_deleted=True) or user
                self.repo.revoke_user_sessions(user.id, reason="role_changed")
                events.append(("ROLE_CHANGE", {"from": previous_role, "to": payload.role}))

        if payload.is_active is not None:
            if user.role.name == "ADMIN" and payload.is_active is False:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Un administrateur ne peut pas etre desactive.",
                )
            if user.is_active != payload.is_active:
                user.is_active = payload.is_active
                if payload.is_active is False:
                    self.repo.revoke_user_sessions(user.id, reason="user_deactivated")
                events.append(("USER_UPDATE", {"field": "is_active", "value": payload.is_active}))

        if payload.password is not None:
            user.password_hash = hash_password(payload.password)
            user.password_changed_at = datetime.now(UTC)
            self.repo.revoke_user_sessions(user.id, reason="password_changed")
            events.append(("PASSWORD_CHANGE", {"trigger": "admin_reset"}))

        if not events:
            return self._serialize_user(user)

        for action, metadata in events:
            self._audit(
                action=action,
                status_value="SUCCESS",
                client=client,
                actor_user_id=actor.id,
                target_user_id=user.id,
                metadata=metadata,
            )

        self.db.commit()
        refreshed = self.repo.get_user_by_id(user.id, include_deleted=True)
        if refreshed is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable.")
        return self._serialize_user(refreshed)

    def soft_delete_user(self, actor: AuthenticatedPrincipal, user_id: int, *, client: ClientContext) -> None:
        user = self.repo.get_user_by_id(user_id, include_deleted=True)
        if user is None or user.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable.")
        if user.role.name == "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Un administrateur ne peut pas etre supprime.",
            )
        if actor.id == user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Un administrateur ne peut pas supprimer son propre compte.",
            )

        user.is_active = False
        user.deleted_at = datetime.now(UTC)
        self.repo.revoke_user_sessions(user.id, reason="user_deleted")
        self._audit(
            action="USER_DELETE",
            status_value="SUCCESS",
            client=client,
            actor_user_id=actor.id,
            target_user_id=user.id,
            metadata={"email": user.email},
        )
        self.db.commit()

    def logout(self, access_token: str | None, refresh_token: str | None, *, client: ClientContext) -> None:
        session = None
        actor_id: int | None = None

        for token, expected_type in ((access_token, "access"), (refresh_token, "refresh")):
            if not token:
                continue
            try:
                payload = decode_token(token, expected_type=expected_type)
                session_id = uuid.UUID(str(payload["sid"]))
            except (InvalidTokenError, ValueError):
                continue
            session = self.repo.get_session(session_id)
            if session is not None:
                actor_id = session.user_id
                break

        if session is None:
            return

        self.repo.revoke_session(session, "logout")
        self._audit(
            action="LOGOUT",
            status_value="SUCCESS",
            client=client,
            actor_user_id=actor_id,
            target_user_id=actor_id,
            metadata={"session_id": str(session.id)},
        )
        self.db.commit()


def build_client_context(request: Request) -> ClientContext:
    forwarded_for = request.headers.get("x-forwarded-for")
    ip_address = forwarded_for.split(",")[0].strip() if forwarded_for else request.client.host if request.client else None
    return ClientContext(
        ip_address=ip_address,
        user_agent=request.headers.get("user-agent"),
    )


def get_auth_service(db: Annotated[Session, Depends(get_db)]) -> AuthService:
    return AuthService(db)


def get_current_user(
    access_token: Annotated[str | None, Depends(get_bearer_token)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthenticatedPrincipal:
    return auth_service.get_current_principal(access_token)


def require_roles(*roles: str):
    def checker(current_user: Annotated[AuthenticatedPrincipal, Depends(get_current_user)]) -> AuthenticatedPrincipal:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
        return current_user

    return checker
