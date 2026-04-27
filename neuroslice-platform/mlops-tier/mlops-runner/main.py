"""Internal-only worker that executes a fixed offline MLOps pipeline command.

Security model:
- the command is fixed at startup from MLOPS_PIPELINE_COMMAND
- callers cannot inject arbitrary commands or arguments
- the service is not published outside the compose network
- callers authenticate with a shared bearer token (MLOPS_RUNNER_TOKEN)
"""
from __future__ import annotations

import os
import shlex
import subprocess
import time
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

DEFAULT_COMMAND = "docker compose --profile mlops --profile mlops-worker run --rm mlops-worker"

app = FastAPI(title="NeuroSlice MLOps Runner", version="1.0.0")


class RunPipelineResponse(BaseModel):
    accepted: bool
    exit_code: int | None
    duration_seconds: float
    stdout: str = Field(default="")
    stderr: str = Field(default="")
    command_label: str
    timed_out: bool = False
    detail: str | None = None


def _expected_token() -> str | None:
    return os.getenv("MLOPS_RUNNER_TOKEN") or None


def _enabled() -> bool:
    return os.getenv("MLOPS_PIPELINE_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def _command() -> list[str]:
    raw = os.getenv("MLOPS_PIPELINE_COMMAND", DEFAULT_COMMAND).strip()
    if not raw:
        raw = DEFAULT_COMMAND
    return shlex.split(raw)


def _workdir() -> str:
    return os.getenv("MLOPS_PIPELINE_WORKDIR", "/workspace")


def _timeout_seconds() -> int:
    try:
        return max(60, int(os.getenv("MLOPS_PIPELINE_TIMEOUT_SECONDS", "7200")))
    except ValueError:
        return 7200


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
    return {
        "status": "ok",
        "service": "mlops-runner",
        "enabled": _enabled(),
        "command_label": " ".join(_command()),
    }


@app.post("/run-pipeline", response_model=RunPipelineResponse)
def run_pipeline(_: Annotated[None, Depends(require_runner_token)]) -> RunPipelineResponse:
    if not _enabled():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MLOps pipeline runner is disabled (MLOPS_PIPELINE_ENABLED).",
        )

    argv = _command()
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
        return RunPipelineResponse(
            accepted=True,
            exit_code=None,
            duration_seconds=duration,
            stdout=_truncate(exc.stdout or ""),
            stderr=_truncate(exc.stderr or "Pipeline timed out."),
            command_label=label,
            timed_out=True,
            detail=f"Pipeline timed out after {_timeout_seconds()}s.",
        )
    except FileNotFoundError as exc:
        duration = time.monotonic() - start
        return RunPipelineResponse(
            accepted=False,
            exit_code=None,
            duration_seconds=duration,
            stdout="",
            stderr=str(exc),
            command_label=label,
            timed_out=False,
            detail="Pipeline command binary not found inside mlops-runner.",
        )

    duration = time.monotonic() - start
    return RunPipelineResponse(
        accepted=True,
        exit_code=completed.returncode,
        duration_seconds=duration,
        stdout=_truncate(completed.stdout or ""),
        stderr=_truncate(completed.stderr or ""),
        command_label=label,
        timed_out=False,
    )
