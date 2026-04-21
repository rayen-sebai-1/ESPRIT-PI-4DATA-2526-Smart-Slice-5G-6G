from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Response, status

from common.data import create_user, delete_user, list_users, update_user, verify_user
from common.schemas import (
    AdminCreateUserPayload,
    AdminUpdateUserPayload,
    LoginPayload,
    LoginResponse,
    UserOut,
)
from common.security import create_access_token, get_current_user, require_roles

app = FastAPI(title="NeuroSlice Draft - Auth Service", version="1.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "auth-service"}


@app.post("/auth/login", response_model=LoginResponse, tags=["auth"])
def login(payload: LoginPayload) -> LoginResponse:
    user = verify_user(payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe invalide.",
        )
    token, expires_in = create_access_token(user)
    return LoginResponse(access_token=token, expires_in=expires_in, user=user)


@app.get("/auth/me", response_model=UserOut, tags=["auth"])
def me(current_user: Annotated[UserOut, Depends(get_current_user)]) -> UserOut:
    return current_user


@app.get("/users", response_model=list[UserOut], tags=["users"])
def users(_: Annotated[UserOut, Depends(require_roles("ADMIN"))]) -> list[UserOut]:
    return list_users()


@app.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    tags=["users"],
)
def admin_create_user(
    payload: AdminCreateUserPayload,
    _: Annotated[UserOut, Depends(require_roles("ADMIN"))],
) -> UserOut:
    try:
        return create_user(
            full_name=payload.full_name,
            email=payload.email,
            password=payload.password,
            role=payload.role,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@app.patch("/users/{user_id}", response_model=UserOut, tags=["users"])
def admin_update_user(
    user_id: int,
    payload: AdminUpdateUserPayload,
    _: Annotated[UserOut, Depends(require_roles("ADMIN"))],
) -> UserOut:
    try:
        return update_user(
            user_id=user_id,
            full_name=payload.full_name,
            role=payload.role,
            is_active=payload.is_active,
            password=payload.password,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    tags=["users"],
)
def admin_delete_user(
    user_id: int,
    current: Annotated[UserOut, Depends(require_roles("ADMIN"))],
) -> Response:
    if current.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un administrateur ne peut pas supprimer son propre compte.",
        )
    try:
        delete_user(user_id=user_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
