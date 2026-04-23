from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

ALGORITHM = "HS256"
TOKEN_ISSUER = "neuroslice-auth"

bearer = HTTPBearer(auto_error=False)


class InvalidTokenError(ValueError):
    pass


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} must be configured.")
    return value


@lru_cache(maxsize=1)
def get_dashboard_provider_name() -> str:
    return os.getenv("DASHBOARD_DATA_PROVIDER", "temporary_mock").strip().lower()


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            _require_env("JWT_SECRET_KEY"),
            algorithms=[ALGORITHM],
            issuer=TOKEN_ISSUER,
            options={"require": ["exp", "iat", "nbf", "iss", "sub", "sid", "role", "type"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Token validation failed.") from exc

    if payload.get("type") != "access":
        raise InvalidTokenError("Unexpected token type.")

    return payload


def get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str | None:
    return credentials.credentials if credentials else None


def require_access_token(access_token: str | None) -> str:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token manquant.")
    return access_token
