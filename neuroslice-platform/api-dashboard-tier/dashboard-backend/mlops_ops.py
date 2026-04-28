"""MLOps Operations Center backend logic.

Responsibilities:
- expose configured tool URLs (MLflow, MinIO, Kibana, InfluxDB, Grafana, mlops-api)
- check tool health concurrently with bounded timeouts
- launch the offline pipeline by delegating to the internal mlops-runner service
- persist pipeline run history in the dashboard.mlops_pipeline_runs table
- redact secrets from captured stdout/stderr before storing logs
"""
from __future__ import annotations

import os
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import MlopsPipelineRun
from schemas import (
    AuthenticatedPrincipal,
    MlopsPipelineRunLogsResponse,
    MlopsPipelineRunResponse,
    MlopsToolHealth,
    MlopsToolLink,
    MlopsToolsHealthResponse,
    MlopsToolsResponse,
)

DEFAULT_PIPELINE_COMMAND = (
    "docker compose --profile mlops --profile mlops-worker run --rm mlops-worker"
)


@dataclass(frozen=True)
class _ToolDef:
    key: str
    name: str
    env_url: str
    env_health: str
    default_url: str
    default_health: str
    description: str


_TOOLS: tuple[_ToolDef, ...] = (
    _ToolDef(
        key="mlflow",
        name="MLflow",
        env_url="MLOPS_TOOLS_MLFLOW_URL",
        env_health="MLOPS_TOOLS_MLFLOW_HEALTH_URL",
        default_url="http://localhost:5000",
        default_health="http://mlflow-server:5000/health",
        description="Tracking UI and model registry",
    ),
    _ToolDef(
        key="minio",
        name="MinIO",
        env_url="MLOPS_TOOLS_MINIO_URL",
        env_health="MLOPS_TOOLS_MINIO_HEALTH_URL",
        default_url="http://localhost:9001",
        default_health="http://minio:9000/minio/health/live",
        description="S3-compatible artifact storage console",
    ),
    _ToolDef(
        key="kibana",
        name="Kibana",
        env_url="MLOPS_TOOLS_KIBANA_URL",
        env_health="MLOPS_TOOLS_KIBANA_HEALTH_URL",
        default_url="http://localhost:5601",
        default_health="http://kibana:5601/api/status",
        description="Prediction log explorer",
    ),
    _ToolDef(
        key="influxdb",
        name="InfluxDB",
        env_url="MLOPS_TOOLS_INFLUXDB_URL",
        env_health="MLOPS_TOOLS_INFLUXDB_HEALTH_URL",
        default_url="http://localhost:8086",
        default_health="http://influxdb:8086/health",
        description="Time-series telemetry",
    ),
    _ToolDef(
        key="grafana",
        name="Grafana",
        env_url="MLOPS_TOOLS_GRAFANA_URL",
        env_health="MLOPS_TOOLS_GRAFANA_HEALTH_URL",
        default_url="http://localhost:3000",
        default_health="http://grafana:3000/api/health",
        description="Operational dashboards",
    ),
    _ToolDef(
        key="mlops_api",
        name="MLOps API",
        env_url="MLOPS_TOOLS_MLOPS_API_URL",
        env_health="MLOPS_TOOLS_MLOPS_API_HEALTH_URL",
        default_url="http://localhost:8010/docs",
        default_health="http://mlops-api:8010/health",
        description="Prediction and lifecycle API",
    ),
)


# Patterns that should be masked in captured stdout/stderr before persisting.
# Each pattern's replacement string uses backrefs to keep surrounding context.
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


class MlopsOpsConfig:
    """Snapshot of MLOps Operations env config; cheap to construct per request."""

    def __init__(self) -> None:
        self.tools: list[MlopsToolLink] = []
        self._health_urls: dict[str, str] = {}
        for tool in _TOOLS:
            url = (os.getenv(tool.env_url) or tool.default_url).strip() or tool.default_url
            health = (os.getenv(tool.env_health) or tool.default_health).strip() or tool.default_health
            self.tools.append(
                MlopsToolLink(key=tool.key, name=tool.name, url=url, description=tool.description)
            )
            self._health_urls[tool.key] = health

        self.pipeline_enabled: bool = (
            os.getenv("MLOPS_PIPELINE_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
        )
        self.pipeline_runner_url: str | None = (os.getenv("MLOPS_RUNNER_URL") or "").strip() or None
        self.pipeline_runner_token: str | None = (os.getenv("MLOPS_RUNNER_TOKEN") or "").strip() or None
        self.pipeline_command_label: str = (
            os.getenv("MLOPS_PIPELINE_COMMAND", DEFAULT_PIPELINE_COMMAND).strip()
            or DEFAULT_PIPELINE_COMMAND
        )
        try:
            self.pipeline_timeout_seconds: int = max(
                60, int(os.getenv("MLOPS_PIPELINE_TIMEOUT_SECONDS", "7200"))
            )
        except ValueError:
            self.pipeline_timeout_seconds = 7200

    def tool_health_url(self, key: str) -> str | None:
        return self._health_urls.get(key)


def _check_one(tool: MlopsToolLink, health_url: str | None, timeout: float) -> MlopsToolHealth:
    if not health_url:
        return MlopsToolHealth(name=tool.name, url=tool.url, status="UNKNOWN", detail="No health URL configured.")
    started = time.monotonic()
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(health_url)
        latency_ms = int((time.monotonic() - started) * 1000)
        if 200 <= response.status_code < 500:
            status = "UP" if response.status_code < 400 else "DOWN"
            return MlopsToolHealth(
                name=tool.name,
                url=tool.url,
                status=status,
                latency_ms=latency_ms,
                detail=f"HTTP {response.status_code}",
            )
        return MlopsToolHealth(
            name=tool.name,
            url=tool.url,
            status="DOWN",
            latency_ms=latency_ms,
            detail=f"HTTP {response.status_code}",
        )
    except httpx.HTTPError as exc:
        return MlopsToolHealth(
            name=tool.name,
            url=tool.url,
            status="DOWN",
            latency_ms=None,
            detail=f"{type(exc).__name__}",
        )


class MlopsOpsService:
    def __init__(
        self,
        db: Session,
        *,
        config: MlopsOpsConfig | None = None,
        http_client_factory=None,
    ) -> None:
        self.db = db
        self.config = config or MlopsOpsConfig()
        self._http_client_factory = http_client_factory

    # ---- Tool inventory ---------------------------------------------------

    def list_tools(self) -> MlopsToolsResponse:
        return MlopsToolsResponse(tools=self.config.tools)

    def check_tool_health(self, *, timeout: float = 2.0) -> MlopsToolsHealthResponse:
        tools = self.config.tools
        with ThreadPoolExecutor(max_workers=max(1, len(tools))) as executor:
            results = list(
                executor.map(
                    lambda tool: _check_one(tool, self.config.tool_health_url(tool.key), timeout),
                    tools,
                )
            )
        return MlopsToolsHealthResponse(services=results)

    # ---- Pipeline run history --------------------------------------------

    def list_runs(self, *, limit: int = 50) -> list[MlopsPipelineRunResponse]:
        statement = (
            select(MlopsPipelineRun)
            .order_by(MlopsPipelineRun.created_at.desc())
            .limit(max(1, min(limit, 200)))
        )
        rows = list(self.db.scalars(statement))
        return [self._to_run_response(row) for row in rows]

    def get_run(self, run_id: str) -> MlopsPipelineRun | None:
        try:
            uid = uuid.UUID(run_id)
        except ValueError:
            return None
        return self.db.get(MlopsPipelineRun, uid)

    def get_run_response(self, run_id: str) -> MlopsPipelineRunResponse | None:
        row = self.get_run(run_id)
        if row is None:
            return None
        return self._to_run_response(row)

    def get_run_logs(self, run_id: str) -> MlopsPipelineRunLogsResponse | None:
        row = self.get_run(run_id)
        if row is None:
            return None
        return MlopsPipelineRunLogsResponse(
            run_id=str(row.id),
            status=row.status,  # type: ignore[arg-type]
            stdout=row.stdout_log or "",
            stderr=row.stderr_log or "",
        )

    # ---- Pipeline launch --------------------------------------------------

    def create_run(self, principal: AuthenticatedPrincipal) -> MlopsPipelineRun:
        run = MlopsPipelineRun(
            triggered_by_user_id=principal.id,
            triggered_by_email=principal.email,
            status="QUEUED",
            command_label=self.config.pipeline_command_label,
        )
        self.db.add(run)
        self.db.flush()
        self.db.commit()
        self.db.refresh(run)
        return run

    def mark_disabled(self, run_id: uuid.UUID) -> None:
        row = self.db.get(MlopsPipelineRun, run_id)
        if row is None:
            return
        row.status = "DISABLED"
        row.finished_at = datetime.now(UTC)
        row.stderr_log = "MLOps pipeline runner is disabled (MLOPS_PIPELINE_ENABLED)."
        self.db.commit()

    def execute_run(self, run_id: uuid.UUID) -> None:
        """Blocking call meant for a background thread/task."""
        row = self.db.get(MlopsPipelineRun, run_id)
        if row is None:
            return

        if not self.config.pipeline_enabled:
            row.status = "DISABLED"
            row.finished_at = datetime.now(UTC)
            row.stderr_log = "MLOps pipeline runner is disabled (MLOPS_PIPELINE_ENABLED)."
            self.db.commit()
            return

        if not self.config.pipeline_runner_url:
            row.status = "FAILED"
            row.finished_at = datetime.now(UTC)
            row.stderr_log = "MLOPS_RUNNER_URL is not configured."
            self.db.commit()
            return

        row.status = "RUNNING"
        row.started_at = datetime.now(UTC)
        self.db.commit()

        headers: dict[str, str] = {}
        if self.config.pipeline_runner_token:
            headers["Authorization"] = f"Bearer {self.config.pipeline_runner_token}"

        timeout = self.config.pipeline_timeout_seconds + 30
        client_factory = self._http_client_factory or (lambda: httpx.Client(timeout=timeout))

        stdout = ""
        stderr = ""
        exit_code: int | None = None
        timed_out = False
        ok = False

        try:
            with client_factory() as client:
                response = client.post(
                    f"{self.config.pipeline_runner_url.rstrip('/')}/run-pipeline",
                    headers=headers,
                )
                response.raise_for_status()
                payload = response.json()
            stdout = str(payload.get("stdout") or "")
            stderr = str(payload.get("stderr") or "")
            exit_code = payload.get("exit_code")
            timed_out = bool(payload.get("timed_out"))
            ok = bool(payload.get("accepted"))
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
        row.exit_code = exit_code if isinstance(exit_code, int) else None
        row.stdout_log = redact_log(_truncate(stdout))
        row.stderr_log = redact_log(_truncate(stderr))
        self.db.commit()

    # ---- Helpers ---------------------------------------------------------

    @staticmethod
    def _to_run_response(row: MlopsPipelineRun) -> MlopsPipelineRunResponse:
        duration: float | None = None
        if row.started_at and row.finished_at:
            duration = max(0.0, (row.finished_at - row.started_at).total_seconds())
        return MlopsPipelineRunResponse(
            run_id=str(row.id),
            triggered_by_user_id=row.triggered_by_user_id,
            triggered_by_email=row.triggered_by_email,
            status=row.status,  # type: ignore[arg-type]
            command_label=row.command_label,
            started_at=row.started_at,
            finished_at=row.finished_at,
            exit_code=row.exit_code,
            duration_seconds=duration,
            created_at=row.created_at,
        )


def background_execute_run(run_id: uuid.UUID) -> None:
    """Background task entry point.

    FastAPI BackgroundTasks runs sync callables in the threadpool, so this
    function opens its own SQLAlchemy session rather than reusing the
    request-scoped one (which is closed by the time the task runs).
    """
    from db import get_session_factory

    session_factory = get_session_factory()
    session = session_factory()
    try:
        MlopsOpsService(session).execute_run(run_id)
    finally:
        session.close()
