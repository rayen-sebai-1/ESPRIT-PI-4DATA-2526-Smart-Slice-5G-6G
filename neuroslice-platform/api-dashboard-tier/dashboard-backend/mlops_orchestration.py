from __future__ import annotations

import os
import re
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import MlopsOrchestrationRun
from schemas import (
    AuthenticatedPrincipal,
    MlopsActionDefinition,
    MlopsOrchestrationRunLogsResponse,
    MlopsOrchestrationRunResponse,
)

# Redaction patterns from mlops_ops.py
_REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)(password\s*[=:]\s*)([^\s'\";]+)"), r"\1***"),
    (re.compile(r"(?i)(secret\s*[=:]\s*)([^\s'\";]+)"), r"\1***"),
    (re.compile(r"(?i)(token\s*[=:]\s*)([^\s'\";]+)"), r"\1***"),
    (re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)([^\s'\";]+)"), r"\1***"),
    (re.compile(r"(?i)(access[_-]?key[_-]?id\s*[=:]\s*)([^\s'\";]+)"), r"\1***"),
    (re.compile(r"(?i)(secret[_-]?access[_-]?key\s*[=:]\s*)([^\s'\";]+)"), r"\1***"),
    (re.compile(r"(?i)(authorization\s*:\s*bearer\s+)(\S+)"), r"\1***"),
    (
        re.compile(
            r"((?:postgres(?:ql)?|mysql|mongodb|redis|amqp)\+?\w*://[^:\s]+:)([^@\s]+)(@)"
        ),
        r"\1***\3",
    ),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}\b"), "***JWT***"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "***AWS_KEY***"),
)


def redact_log(value: str | None) -> str:
    if not value:
        return ""
    redacted = value
    for pattern, replacement in _REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _truncate(value: str, *, limit: int = 200_000) -> str:
    if len(value) <= limit:
        return value
    head = value[: limit // 2]
    tail = value[-limit // 2 :]
    return f"{head}\n... [truncated {len(value) - limit} chars] ...\n{tail}"


_ALLOWED_ACTIONS: dict[str, MlopsActionDefinition] = {
    "prepare_data": MlopsActionDefinition(
        action_key="prepare_data",
        label="Prepare Data",
        description="Extract and preprocess raw data into model-ready datasets.",
        risk_level="LOW",
        requires_confirmation=False,
        allowed_roles=["ADMIN", "DATA_MLOPS_ENGINEER"],
    ),
    "validate_data": MlopsActionDefinition(
        action_key="validate_data",
        label="Validate Data",
        description="Run data quality checks on preprocessed datasets.",
        risk_level="LOW",
        requires_confirmation=False,
        allowed_roles=["ADMIN", "DATA_MLOPS_ENGINEER"],
    ),
    "train": MlopsActionDefinition(
        action_key="train",
        label="Train Model",
        description="Train models based on prepared data.",
        risk_level="MEDIUM",
        requires_confirmation=False,
        allowed_roles=["ADMIN", "DATA_MLOPS_ENGINEER"],
    ),
    "evaluate": MlopsActionDefinition(
        action_key="evaluate",
        label="Evaluate Model",
        description="Evaluate models against holdout sets and baseline.",
        risk_level="LOW",
        requires_confirmation=False,
        allowed_roles=["ADMIN", "DATA_MLOPS_ENGINEER"],
    ),
    "log_mlflow": MlopsActionDefinition(
        action_key="log_mlflow",
        label="Log to MLflow",
        description="Log models, parameters, and metrics to MLflow registry.",
        risk_level="LOW",
        requires_confirmation=False,
        allowed_roles=["ADMIN", "DATA_MLOPS_ENGINEER"],
    ),
    "export_onnx": MlopsActionDefinition(
        action_key="export_onnx",
        label="Export ONNX",
        description="Export trained models to ONNX format for serving.",
        risk_level="MEDIUM",
        requires_confirmation=False,
        allowed_roles=["ADMIN", "DATA_MLOPS_ENGINEER"],
    ),
    "convert_fp16": MlopsActionDefinition(
        action_key="convert_fp16",
        label="Convert FP16",
        description="Quantize ONNX models to FP16 for optimized inference.",
        risk_level="MEDIUM",
        requires_confirmation=False,
        allowed_roles=["ADMIN", "DATA_MLOPS_ENGINEER"],
    ),
    "validate_model": MlopsActionDefinition(
        action_key="validate_model",
        label="Validate Model",
        description="Validate exported artifacts via quality gates.",
        risk_level="LOW",
        requires_confirmation=False,
        allowed_roles=["ADMIN", "DATA_MLOPS_ENGINEER"],
    ),
    "promote_model": MlopsActionDefinition(
        action_key="promote_model",
        label="Promote Model",
        description="Promote a validated model to production.",
        risk_level="HIGH",
        requires_confirmation=True,
        allowed_roles=["ADMIN", "DATA_MLOPS_ENGINEER"],
    ),
    "rollback_model": MlopsActionDefinition(
        action_key="rollback_model",
        label="Rollback Model",
        description="Rollback a production model to a previous version.",
        risk_level="HIGH",
        requires_confirmation=True,
        allowed_roles=["ADMIN", "DATA_MLOPS_ENGINEER"],
    ),
    "full_pipeline": MlopsActionDefinition(
        action_key="full_pipeline",
        label="Run Full Pipeline",
        description="Run the complete safe pipeline sequence (prepare to validate_model).",
        risk_level="HIGH",
        requires_confirmation=True,
        allowed_roles=["ADMIN", "DATA_MLOPS_ENGINEER"],
    ),
}


class MlopsOrchestrationConfig:
    def __init__(self) -> None:
        self.orchestration_enabled: bool = (
            os.getenv("MLOPS_ORCHESTRATION_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
        )
        self.runner_url: str | None = (os.getenv("MLOPS_RUNNER_URL") or "").strip() or None
        self.runner_token: str | None = (os.getenv("MLOPS_RUNNER_TOKEN") or "").strip() or None
        
        try:
            self.timeout_seconds: int = max(
                60, int(os.getenv("MLOPS_ORCHESTRATION_TIMEOUT_SECONDS", "7200"))
            )
        except ValueError:
            self.timeout_seconds = 7200


class MlopsOrchestrationService:
    def __init__(
        self,
        db: Session,
        *,
        config: MlopsOrchestrationConfig | None = None,
        http_client_factory=None,
    ) -> None:
        self.db = db
        self.config = config or MlopsOrchestrationConfig()
        self._http_client_factory = http_client_factory

    def list_actions(self) -> list[MlopsActionDefinition]:
        return list(_ALLOWED_ACTIONS.values())

    def get_action_definition(self, action_key: str) -> MlopsActionDefinition | None:
        return _ALLOWED_ACTIONS.get(action_key)

    def list_runs(self, *, limit: int = 50) -> list[MlopsOrchestrationRunResponse]:
        statement = (
            select(MlopsOrchestrationRun)
            .order_by(MlopsOrchestrationRun.created_at.desc())
            .limit(max(1, min(limit, 200)))
        )
        rows = list(self.db.scalars(statement))
        return [self._to_run_response(row) for row in rows]

    def get_run(self, run_id: str) -> MlopsOrchestrationRun | None:
        try:
            uid = uuid.UUID(run_id)
        except ValueError:
            return None
        return self.db.get(MlopsOrchestrationRun, uid)

    def get_run_response(self, run_id: str) -> MlopsOrchestrationRunResponse | None:
        row = self.get_run(run_id)
        if row is None:
            return None
        return self._to_run_response(row)

    def get_run_logs(self, run_id: str) -> MlopsOrchestrationRunLogsResponse | None:
        row = self.get_run(run_id)
        if row is None:
            return None
        return MlopsOrchestrationRunLogsResponse(
            run_id=str(row.id),
            status=row.status,  # type: ignore[arg-type]
            stdout=row.stdout_log or "",
            stderr=row.stderr_log or "",
        )

    def create_run(
        self,
        principal: AuthenticatedPrincipal,
        action_key: str,
        parameters: dict[str, Any],
        trigger_source: str = "manual",
    ) -> MlopsOrchestrationRun:
        action_def = self.get_action_definition(action_key)
        if not action_def:
            raise ValueError(f"Unknown action: {action_key}")

        safe_source = trigger_source if trigger_source in {"manual", "drift", "scheduled"} else "manual"

        # Ensure parameters only contain safe types (strings, ints, floats, bools)
        safe_params = {}
        for k, v in parameters.items():
            if isinstance(v, (str, int, float, bool)):
                safe_params[k] = v

        run = MlopsOrchestrationRun(
            action_key=action_key,
            command_label=action_def.label,
            parameters_json=safe_params,
            triggered_by_user_id=principal.id,
            triggered_by_email=principal.email,
            trigger_source=safe_source,
            status="QUEUED",
        )
        self.db.add(run)
        self.db.flush()
        self.db.commit()
        self.db.refresh(run)
        return run

    def execute_run(self, run_id: uuid.UUID) -> None:
        """Blocking call meant for a background thread/task."""
        row = self.db.get(MlopsOrchestrationRun, run_id)
        if row is None:
            return

        if not self.config.orchestration_enabled:
            row.status = "DISABLED"
            row.finished_at = datetime.now(UTC)
            row.stderr_log = "MLOps orchestration is disabled (MLOPS_ORCHESTRATION_ENABLED)."
            self.db.commit()
            return

        if not self.config.runner_url:
            row.status = "FAILED"
            row.finished_at = datetime.now(UTC)
            row.stderr_log = "MLOPS_RUNNER_URL is not configured."
            self.db.commit()
            return

        row.status = "RUNNING"
        row.started_at = datetime.now(UTC)
        self.db.commit()

        headers: dict[str, str] = {}
        if self.config.runner_token:
            headers["Authorization"] = f"Bearer {self.config.runner_token}"

        timeout = self.config.timeout_seconds + 30
        client_factory = self._http_client_factory or (lambda: httpx.Client(timeout=timeout))

        stdout = ""
        stderr = ""
        exit_code: int | None = None
        timed_out = False
        ok = False

        payload = {
            "action": row.action_key,
            "parameters": row.parameters_json,
            "trigger_source": row.trigger_source or "manual",
        }

        try:
            with client_factory() as client:
                response = client.post(
                    f"{self.config.runner_url.rstrip('/')}/run-action",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                response_payload = response.json()
            stdout = str(response_payload.get("stdout") or "")
            stderr = str(response_payload.get("stderr") or "")
            exit_code = response_payload.get("exit_code")
            timed_out = bool(response_payload.get("timed_out"))
            ok = bool(response_payload.get("accepted"))
        except httpx.HTTPError as exc:
            stderr = f"mlops-runner call failed: {type(exc).__name__}: {exc}"
        except ValueError as exc:
            stderr = f"mlops-runner returned invalid JSON: {exc}"

        finished_at = datetime.now(UTC)

        if timed_out:
            status = "TIMEOUT"
        elif not ok:
            status = "FAILED"
        elif isinstance(exit_code, int):
            status = "SUCCESS" if exit_code == 0 else "FAILED"
        else:
            status = "FAILED"

        row.status = status
        row.finished_at = finished_at
        row.duration_seconds = max(0.0, (finished_at - row.started_at).total_seconds()) if row.started_at else None
        row.exit_code = exit_code if isinstance(exit_code, int) else None
        row.stdout_log = redact_log(_truncate(stdout))
        row.stderr_log = redact_log(_truncate(stderr))
        self.db.commit()

    @staticmethod
    def _to_run_response(row: MlopsOrchestrationRun) -> MlopsOrchestrationRunResponse:
        return MlopsOrchestrationRunResponse(
            run_id=str(row.id),
            action_key=row.action_key,
            command_label=row.command_label,
            parameters=row.parameters_json,  # type: ignore
            triggered_by_user_id=row.triggered_by_user_id,
            triggered_by_email=row.triggered_by_email,
            trigger_source=row.trigger_source or "manual",
            status=row.status,  # type: ignore[arg-type]
            started_at=row.started_at,
            finished_at=row.finished_at,
            exit_code=row.exit_code,
            duration_seconds=row.duration_seconds,
            created_at=row.created_at,
        )


def background_execute_orchestration_run(run_id: uuid.UUID) -> None:
    from db import get_session_factory

    session_factory = get_session_factory()
    session = session_factory()
    try:
        MlopsOrchestrationService(session).execute_run(run_id)
    finally:
        session.close()
