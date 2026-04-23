from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response, status

from db import check_database_connection
from schemas import AdminCreateUserPayload, AdminUpdateUserPayload, AuthenticatedPrincipal, LoginPayload, LoginResponse, UserOut
from security import clear_refresh_cookie, get_bearer_token, get_refresh_cookie_name, set_refresh_cookie
from service import AuthService, build_client_context, get_auth_service, get_current_user, require_roles

app = FastAPI(title="NeuroSlice Auth Service", version="2.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    try:
        check_database_connection()
        database_state = "up"
        service_state = "ok"
    except Exception:
        database_state = "down"
        service_state = "degraded"

    return {
        "status": service_state,
        "service": "auth-service",
        "database": database_state,
    }


@app.post("/auth/login", response_model=LoginResponse, tags=["auth"])
def login(
    payload: LoginPayload,
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> LoginResponse:
    bundle = auth_service.authenticate_user(payload.email, payload.password, client=build_client_context(request))
    set_refresh_cookie(response, bundle.refresh_token, bundle.refresh_expires_at)
    return LoginResponse(
        access_token=bundle.access_token,
        expires_in=bundle.expires_in,
        user=bundle.user,
    )


@app.post("/auth/refresh", response_model=LoginResponse, tags=["auth"])
def refresh_session(
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> LoginResponse:
    bundle = auth_service.refresh_session(
        request.cookies.get(get_refresh_cookie_name()),
        client=build_client_context(request),
    )
    set_refresh_cookie(response, bundle.refresh_token, bundle.refresh_expires_at)
    return LoginResponse(
        access_token=bundle.access_token,
        expires_in=bundle.expires_in,
        user=bundle.user,
    )


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["auth"])
def logout(
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    access_token: Annotated[str | None, Depends(get_bearer_token)],
) -> Response:
    auth_service.logout(
        access_token,
        request.cookies.get(get_refresh_cookie_name()),
        client=build_client_context(request),
    )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(response)
    return response


@app.get("/auth/me", response_model=UserOut, tags=["auth"])
def me(current_user: Annotated[AuthenticatedPrincipal, Depends(get_current_user)]) -> UserOut:
    return UserOut(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
    )


@app.get("/users", response_model=list[UserOut], tags=["users"])
def users(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    _: Annotated[AuthenticatedPrincipal, Depends(require_roles("ADMIN"))],
) -> list[UserOut]:
    return auth_service.list_users()


@app.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED, tags=["users"])
def admin_create_user(
    payload: AdminCreateUserPayload,
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    current_user: Annotated[AuthenticatedPrincipal, Depends(require_roles("ADMIN"))],
) -> UserOut:
    return auth_service.create_user(current_user, payload, client=build_client_context(request))


@app.patch("/users/{user_id}", response_model=UserOut, tags=["users"])
def admin_update_user(
    user_id: int,
    payload: AdminUpdateUserPayload,
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    current_user: Annotated[AuthenticatedPrincipal, Depends(require_roles("ADMIN"))],
) -> UserOut:
    return auth_service.update_user(current_user, user_id, payload, client=build_client_context(request))


@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["users"])
def admin_delete_user(
    user_id: int,
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    current_user: Annotated[AuthenticatedPrincipal, Depends(require_roles("ADMIN"))],
) -> Response:
    auth_service.soft_delete_user(current_user, user_id, client=build_client_context(request))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
