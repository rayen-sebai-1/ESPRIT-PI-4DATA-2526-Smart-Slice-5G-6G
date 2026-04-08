from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.neuroslice_common.config import get_settings
from packages.neuroslice_common.db import get_db
from packages.neuroslice_common.enums import UserRole
from packages.neuroslice_common.models import User
from packages.neuroslice_common.security import create_access_token, get_current_user, require_roles, verify_password
from services.auth_service.app.schemas import LoginRequest, TokenResponse, UserResponse

settings = get_settings()

app = FastAPI(
    title="NeuroSlice Tunisia - Auth Service",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/auth/login", response_model=TokenResponse, tags=["auth"])
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe invalide.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Utilisateur désactivé.")

    token, expires_in = create_access_token(user_id=user.id, email=user.email, role=user.role)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


@app.get("/auth/me", response_model=UserResponse, tags=["auth"])
def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.model_validate(current_user)


@app.get("/users", response_model=list[UserResponse], tags=["users"])
def list_users(
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> list[UserResponse]:
    users = db.scalars(select(User).order_by(User.id)).all()
    return [UserResponse.model_validate(user) for user in users]
