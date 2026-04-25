from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CopilotQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, description="NOC operator natural-language question.")
    session_id: str = Field(..., min_length=1, description="Conversation/session identifier.")

    @field_validator("query", "session_id")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must be a non-empty string")
        return normalized


class SSEErrorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class CopilotQueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    answer: str
