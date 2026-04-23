from __future__ import annotations

import hashlib
import os
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from argon2.low_level import Type
from fastapi import Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

ALGORITHM = "HS256"
TOKEN_ISSUER = "neuroslice-auth"
REFRESH_SAMESITE_VALUES = {"lax", "strict", "none"}

bearer = HTTPBearer(auto_error=False)


class InvalidTokenError(ValueError):
    pass


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} must be configured.")
    return value


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = int(raw)
    if value <= 0:
        raise RuntimeError(f"{name} must be greater than zero.")
    return value


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def get_access_token_expiry_minutes() -> int:
    return _env_int("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", 15)


def get_refresh_token_expiry_days() -> int:
    return _env_int("JWT_REFRESH_TOKEN_EXPIRES_DAYS", 7)


def get_refresh_cookie_name() -> str:
    return os.getenv("REFRESH_COOKIE_NAME", "neuroslice_refresh_token")


def get_refresh_cookie_path() -> str:
    return os.getenv("REFRESH_COOKIE_PATH", "/api/auth")


def get_refresh_cookie_samesite() -> Literal["lax", "strict", "none"]:
    value = os.getenv("REFRESH_COOKIE_SAMESITE", "lax").strip().lower()
    if value not in REFRESH_SAMESITE_VALUES:
        raise RuntimeError("REFRESH_COOKIE_SAMESITE must be one of lax, strict, or none.")
    return value  # type: ignore[return-value]


def get_refresh_cookie_secure() -> bool:
    return _env_bool("REFRESH_COOKIE_SECURE", False)


@lru_cache(maxsize=1)
def get_password_hasher() -> PasswordHasher:
    return PasswordHasher(
        time_cost=_env_int("ARGON2_TIME_COST", 3),
        memory_cost=_env_int("ARGON2_MEMORY_COST", 65536),
        parallelism=_env_int("ARGON2_PARALLELISM", 4),
        type=Type.ID,
    )


def hash_password(password: str) -> str:
    return get_password_hasher().hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bool(get_password_hasher().verify(password_hash, password))
    except (VerifyMismatchError, InvalidHashError):
        return False


def _jwt_secret() -> str:
    return _require_env("JWT_SECRET_KEY")


def _build_claims(
    *,
    user_id: int,
    session_id: uuid.UUID,
    role: str,
    token_type: str,
    expires_at: datetime,
) -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "iss": TOKEN_ISSUER,
        "sub": str(user_id),
        "sid": str(session_id),
        "role": role,
        "type": token_type,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }


def create_access_token(*, user_id: int, session_id: uuid.UUID, role: str) -> tuple[str, int]:
    expires_in = get_access_token_expiry_minutes() * 60
    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
    token = jwt.encode(
        _build_claims(
            user_id=user_id,
            session_id=session_id,
            role=role,
            token_type="access",
            expires_at=expires_at,
        ),
        _jwt_secret(),
        algorithm=ALGORITHM,
    )
    return token, expires_in


def create_refresh_token(*, user_id: int, session_id: uuid.UUID, role: str) -> tuple[str, datetime]:
    expires_at = datetime.now(UTC) + timedelta(days=get_refresh_token_expiry_days())
    token = jwt.encode(
        _build_claims(
            user_id=user_id,
            session_id=session_id,
            role=role,
            token_type="refresh",
            expires_at=expires_at,
        ),
        _jwt_secret(),
        algorithm=ALGORITHM,
    )
    return token, expires_at


def decode_token(token: str, *, expected_type: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=[ALGORITHM],
            issuer=TOKEN_ISSUER,
            options={"require": ["exp", "iat", "nbf", "iss", "sub", "sid", "role", "type"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Token validation failed.") from exc

    if payload.get("type") != expected_type:
        raise InvalidTokenError("Unexpected token type.")

    return payload


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str | None:
    return credentials.credentials if credentials else None


def set_refresh_cookie(response: Response, token: str, expires_at: datetime) -> None:
    max_age = max(0, int((expires_at - datetime.now(UTC)).total_seconds()))
    response.set_cookie(
        key=get_refresh_cookie_name(),
        value=token,
        httponly=True,
        secure=get_refresh_cookie_secure(),
        samesite=get_refresh_cookie_samesite(),
        path=get_refresh_cookie_path(),
        max_age=max_age,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=get_refresh_cookie_name(),
        path=get_refresh_cookie_path(),
        secure=get_refresh_cookie_secure(),
        samesite=get_refresh_cookie_samesite(),
    )


def require_access_token(access_token: str | None) -> str:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token manquant.")
    return access_token
