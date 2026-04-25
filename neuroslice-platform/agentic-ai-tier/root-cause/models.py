from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DomainEnum(str, Enum):
    core = "core"
    edge = "edge"
    ran = "ran"


class TimeRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str = Field(default="-30m", min_length=1, description="Flux range start")
    stop: str = Field(default="now()", min_length=1, description="Flux range stop")

    @field_validator("start", "stop")
    @classmethod
    def validate_non_empty_string(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("time_range values must be non-empty strings")
        return normalized


class ManualScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slice_id: str = Field(..., min_length=1, description="Slice identifier")
    domain: Optional[DomainEnum] = Field(
        default=None,
        description="Optional domain filter: core | edge | ran",
    )
    time_range: TimeRange = Field(default_factory=TimeRange)

    @field_validator("slice_id")
    @classmethod
    def validate_slice_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("slice_id must be a non-empty string")
        return normalized


class ManualScanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(..., min_length=1)
    rootCause: str = Field(..., min_length=1)
    affectedEntities: List[str] = Field(default_factory=list)
    evidenceKpis: Dict[str, Any] = Field(default_factory=dict)
    recommendedAction: List[str] = Field(default_factory=list)

    @field_validator("summary", "rootCause")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("response text fields cannot be empty")
        return normalized


class RCAErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: str
    message: str
    diagnostics: Optional[Dict[str, Any]] = None
