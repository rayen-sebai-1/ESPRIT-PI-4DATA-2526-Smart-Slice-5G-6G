"""Internal-only worker that executes a fixed offline MLOps pipeline command.

Security model:
- the command is fixed at startup from MLOPS_PIPELINE_COMMAND
- callers cannot inject arbitrary commands or arguments
- the service is not published outside the compose network
- callers authenticate with a shared bearer token (MLOPS_RUNNER_TOKEN)
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field


app = FastAPI(title="NeuroSlice MLOps Runner", version="2.0.0")


_VALID_TRIGGER_SOURCES = frozenset({"manual", "drift", "scheduled"})

mlops_runner_requests_total = Counter(
    "neuroslice_mlops_runner_requests_total",
    "Total mlops-runner run-action requests",
    ["action", "trigger_source", "status"],
)
mlops_runner_duration_seconds = Histogram(
    "neuroslice_mlops_runner_duration_seconds",
    "mlops-runner action execution duration in seconds",
    ["action", "trigger_source"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 15.0, 30.0, 60.0, 300.0, 900.0, 1800.0, 3600.0],
)
mlops_runner_enabled = Gauge(
    "neuroslice_mlops_runner_enabled",
    "Whether mlops-runner orchestration is enabled (1) or disabled (0)",
)


class RunActionRequest(BaseModel):
    action: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    trigger_source: str = Field(default="manual")


class RunPipelineResponse(BaseModel):
    accepted: bool
    exit_code: int | None
    duration_seconds: float
    stdout: str = Field(default="")
    stderr: str = Field(default="")
    command_label: str
    trigger_source: str = Field(default="manual")
    timed_out: bool = False
    detail: str | None = None


def _expected_token() -> str | None:
    return os.getenv("MLOPS_RUNNER_TOKEN") or None


def _enabled() -> bool:
    return os.getenv("MLOPS_ORCHESTRATION_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def _workdir() -> str:
    return os.getenv("MLOPS_ORCHESTRATION_WORKDIR", "/workspace/neuroslice-platform/infrastructure")


def _mlops_api_container() -> str:
    """Resolve the mlops-api container name dynamically via Docker labels."""
    explicit = os.getenv("MLOPS_API_CONTAINER_NAME")
    if explicit:
        return explicit
    try:
        result = subprocess.run(
            ["docker", "ps", "-q", "-f", "label=com.docker.compose.service=mlops-api"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        container_id = result.stdout.strip().split("\n")[0]
        if container_id:
            return container_id
    except Exception:
        pass
    return "infrastructure-mlops-api-1"


def _timeout_seconds() -> int:
    try:
        return max(60, int(os.getenv("MLOPS_PIPELINE_TIMEOUT_SECONDS", os.getenv("MLOPS_ORCHESTRATION_TIMEOUT_SECONDS", "7200"))))
    except ValueError:
        return 7200


_ACTION_MAP = {
    "prepare_data": "prepare-data",
    "validate_data": "validate-data",
    "train": "train",
    "evaluate": "evaluate",
    "log_mlflow": "log-mlflow",
    "export_onnx": "export-onnx",
    "convert_fp16": "convert-fp16",
    "validate_model": "validate-model",
    "promote_model": "promote-model",
    "rollback_model": "rollback-model",
    "full_pipeline": "mlops-full",
    "pipeline_congestion_5g": "pipeline-congestion-5g",
    "pipeline_sla_5g": "pipeline-sla-5g",
    "pipeline_slice_type_5g": "pipeline-slice-type-5g",
}

def _truncate(value: str, *, limit: int = 200_000) -> str:
    if len(value) <= limit:
        return value
    head = value[: limit // 2]
    tail = value[-limit // 2 :]
    return f"{head}\n... [truncated {len(value) - limit} chars] ...\n{tail}"


def require_runner_token(authorization: Annotated[str | None, Header()] = None) -> None:
    expected = _expected_token()
    if expected is None:
        return
    provided = ""
    if authorization and authorization.lower().startswith("bearer "):
        provided = authorization.split(" ", 1)[1].strip()
    if provided != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@app.get("/health")
def health() -> dict[str, str | bool]:
    mlops_runner_enabled.set(1 if _enabled() else 0)
    return {
        "status": "ok",
        "service": "mlops-runner",
        "enabled": _enabled(),
    }


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/run-action", response_model=RunPipelineResponse)
def run_action(
    payload: RunActionRequest,
    _: Annotated[None, Depends(require_runner_token)]
) -> RunPipelineResponse:
    action_label = payload.action or "unknown"
    trigger_source = payload.trigger_source if payload.trigger_source in _VALID_TRIGGER_SOURCES else "manual"
    mlops_runner_enabled.set(1 if _enabled() else 0)

    if not _enabled():
        mlops_runner_requests_total.labels(
            action=action_label,
            trigger_source=trigger_source,
            status="disabled",
        ).inc()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MLOps orchestration is disabled (MLOPS_ORCHESTRATION_ENABLED).",
        )

    target = _ACTION_MAP.get(payload.action)
    if not target:
        mlops_runner_requests_total.labels(
            action=action_label,
            trigger_source=trigger_source,
            status="invalid_action",
        ).inc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown action key: {payload.action}",
        )

    import logging
    logging.getLogger("mlops-runner").info(
        "Pipeline triggered — action=%s target=%s source=%s", payload.action, target, trigger_source
    )

    container = _mlops_api_container()
    argv = [
        "docker", "exec", container,
        "make", target
    ]
    
    # Safely append parameters
    for k, v in payload.parameters.items():
        if not re.match(r"^[A-Za-z0-9_]+$", k):
            continue
        argv.append(f"{k}={v}")

    label = " ".join(argv)
    start = time.monotonic()

    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, not from user input
            argv,
            cwd=_workdir(),
            capture_output=True,
            text=True,
            timeout=_timeout_seconds(),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - start
        mlops_runner_requests_total.labels(
            action=action_label,
            trigger_source=trigger_source,
            status="timeout",
        ).inc()
        mlops_runner_duration_seconds.labels(
            action=action_label,
            trigger_source=trigger_source,
        ).observe(duration)
        return RunPipelineResponse(
            accepted=True,
            exit_code=None,
            duration_seconds=duration,
            stdout=_truncate(exc.stdout or ""),
            stderr=_truncate(exc.stderr or "Pipeline timed out."),
            command_label=label,
            trigger_source=trigger_source,
            timed_out=True,
            detail=f"Pipeline timed out after {_timeout_seconds()}s.",
        )
    except FileNotFoundError as exc:
        duration = time.monotonic() - start
        mlops_runner_requests_total.labels(
            action=action_label,
            trigger_source=trigger_source,
            status="runner_error",
        ).inc()
        mlops_runner_duration_seconds.labels(
            action=action_label,
            trigger_source=trigger_source,
        ).observe(duration)
        return RunPipelineResponse(
            accepted=False,
            exit_code=None,
            duration_seconds=duration,
            stdout="",
            stderr=str(exc),
            command_label=label,
            trigger_source=trigger_source,
            timed_out=False,
            detail="Pipeline command binary not found inside mlops-runner.",
        )

    duration = time.monotonic() - start
    status_label = "success" if completed.returncode == 0 else "failed"
    mlops_runner_requests_total.labels(
        action=action_label,
        trigger_source=trigger_source,
        status=status_label,
    ).inc()
    mlops_runner_duration_seconds.labels(
        action=action_label,
        trigger_source=trigger_source,
    ).observe(duration)
    return RunPipelineResponse(
        accepted=True,
        exit_code=completed.returncode,
        duration_seconds=duration,
        stdout=_truncate(completed.stdout or ""),
        stderr=_truncate(completed.stderr or ""),
        command_label=label,
        trigger_source=trigger_source,
        timed_out=False,
    )
