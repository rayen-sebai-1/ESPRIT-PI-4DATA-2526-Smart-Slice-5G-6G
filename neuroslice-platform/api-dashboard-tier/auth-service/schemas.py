from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

UserRole = Literal["ADMIN", "NETWORK_OPERATOR", "NETWORK_MANAGER", "DATA_MLOPS_ENGINEER"]
AssignableRole = Literal["NETWORK_OPERATOR", "NETWORK_MANAGER", "DATA_MLOPS_ENGINEER"]
AuditStatus = Literal["SUCCESS", "FAILURE"]


class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    role: UserRole
    is_active: bool


class LoginPayload(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class AdminCreateUserPayload(BaseModel):
    full_name: str
    email: str
    password: str = Field(min_length=8)
    role: AssignableRole = "NETWORK_OPERATOR"


class AdminUpdateUserPayload(BaseModel):
    full_name: str | None = None
    role: AssignableRole | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8)


class AuthenticatedPrincipal(BaseModel):
    id: int
    session_id: str
    full_name: str
    email: str
    role: UserRole
    is_active: bool


class AuditLogOut(BaseModel):
    id: int
    actor_user_id: int | None
    target_user_id: int | None
    action: str
    status: AuditStatus
    metadata: dict[str, Any]
    created_at: datetime
