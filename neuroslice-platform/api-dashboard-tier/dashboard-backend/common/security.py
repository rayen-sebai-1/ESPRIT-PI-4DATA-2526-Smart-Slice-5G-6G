from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from common.data import find_user_by_email
from common.schemas import UserOut

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "draft-neuroslice-secret")
ALGORITHM = "HS256"
TOKEN_EXPIRES_HOURS = int(os.getenv("TOKEN_EXPIRES_HOURS", "12"))

bearer = HTTPBearer(auto_error=False)


def create_access_token(user: UserOut) -> tuple[str, int]:
    expires_in = TOKEN_EXPIRES_HOURS * 3600
    payload = {
        "sub": user.email,
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRES_HOURS),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, expires_in


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> UserOut:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token manquant.")

    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide.") from exc

    user = find_user_by_email(email or "")
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur invalide.")
    return user


def require_roles(*roles: str) -> Callable[[UserOut], UserOut]:
    def checker(user: UserOut = Depends(get_current_user)) -> UserOut:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acces refuse.")
        return user

    return checker
