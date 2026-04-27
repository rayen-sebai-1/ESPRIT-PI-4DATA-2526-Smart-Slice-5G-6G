from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock

from mlops_ops import MlopsOpsConfig, MlopsOpsService, _check_one, redact_log
from schemas import MlopsToolLink


def test_redact_log_passwords_and_tokens() -> None:
    raw = (
        "starting up\n"
        "PASSWORD=hunter2 something\n"
        "secret: super_secret_value\n"
        "token=eyJhbGciOiJIUzI1NiJ9.aaa.bbb\n"
        "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n"
        "DATABASE_URL=postgresql://user:topsecret@db:5432/app\n"
        "Authorization: Bearer abc.def.ghi\n"
    )
    redacted = redact_log(raw)
    assert "hunter2" not in redacted
    assert "super_secret_value" not in redacted
    assert "topsecret" not in redacted
    assert "abc.def.ghi" not in redacted
    assert "AKIAIOSFODNN7EXAMPLE" not in redacted
    assert "***" in redacted
    assert "***JWT***" in redacted
    assert "***AWS_KEY***" in redacted
    assert "starting up" in redacted  # non-secret content preserved


def test_redact_log_handles_empty() -> None:
    assert redact_log(None) == ""
    assert redact_log("") == ""


def test_config_reads_env(monkeypatch) -> None:
    monkeypatch.setenv("MLOPS_TOOLS_MLFLOW_URL", "http://mlflow.example:5000")
    monkeypatch.setenv("MLOPS_PIPELINE_ENABLED", "true")
    monkeypatch.setenv("MLOPS_PIPELINE_TIMEOUT_SECONDS", "1234")
    monkeypatch.setenv("MLOPS_RUNNER_URL", "http://runner.example:8020")
    monkeypatch.setenv("MLOPS_RUNNER_TOKEN", "abcdef")

    config = MlopsOpsConfig()
    mlflow_tool = next(t for t in config.tools if t.key == "mlflow")
    assert mlflow_tool.url == "http://mlflow.example:5000"
    assert config.pipeline_enabled is True
    assert config.pipeline_timeout_seconds == 1234
    assert config.pipeline_runner_url == "http://runner.example:8020"
    assert config.pipeline_runner_token == "abcdef"


def test_config_pipeline_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("MLOPS_PIPELINE_ENABLED", raising=False)
    config = MlopsOpsConfig()
    assert config.pipeline_enabled is False


def test_check_one_marks_unknown_when_no_url() -> None:
    tool = MlopsToolLink(key="x", name="X", url="http://x", description="")
    result = _check_one(tool, None, timeout=0.1)
    assert result.status == "UNKNOWN"
    assert result.detail == "No health URL configured."


def test_list_tools_uses_config(monkeypatch) -> None:
    monkeypatch.setenv("MLOPS_TOOLS_MLFLOW_URL", "http://mlflow.local:5000")
    db = MagicMock()
    service = MlopsOpsService(db, config=MlopsOpsConfig())
    tools = service.list_tools()
    keys = {t.key for t in tools.tools}
    assert {"mlflow", "minio", "kibana", "influxdb", "grafana", "mlops_api"} == keys
    mlflow_tool = next(t for t in tools.tools if t.key == "mlflow")
    assert mlflow_tool.url == "http://mlflow.local:5000"


def test_execute_run_disabled_when_pipeline_off(monkeypatch) -> None:
    monkeypatch.setenv("MLOPS_PIPELINE_ENABLED", "false")
    db = MagicMock()
    row = MagicMock()
    row.status = "QUEUED"
    db.get.return_value = row

    service = MlopsOpsService(db, config=MlopsOpsConfig())
    import uuid

    service.execute_run(uuid.uuid4())

    assert row.status == "DISABLED"
    assert row.stderr_log
    assert "MLOPS_PIPELINE_ENABLED" in row.stderr_log
    db.commit.assert_called()


def test_execute_run_delegates_and_persists_redacted_output(monkeypatch) -> None:
    monkeypatch.setenv("MLOPS_PIPELINE_ENABLED", "true")
    monkeypatch.setenv("MLOPS_RUNNER_URL", "http://mlops-runner:8020")
    monkeypatch.setenv("MLOPS_RUNNER_TOKEN", "shared")

    db = MagicMock()
    row = MagicMock()
    row.status = "QUEUED"
    row.started_at = None
    db.get.return_value = row

    class _FakeResp:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self._payload

    class _FakeClient:
        def __init__(self):
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def post(self, url, headers=None):
            self.calls.append((url, headers))
            return _FakeResp(
                {
                    "accepted": True,
                    "exit_code": 0,
                    "duration_seconds": 1.5,
                    "stdout": "training ok\nPASSWORD=hunter2 done",
                    "stderr": "",
                    "command_label": "label",
                    "timed_out": False,
                }
            )

    fake = _FakeClient()
    service = MlopsOpsService(
        db,
        config=MlopsOpsConfig(),
        http_client_factory=lambda: fake,
    )
    import uuid

    service.execute_run(uuid.uuid4())

    assert row.status == "SUCCESS"
    assert row.exit_code == 0
    assert "hunter2" not in (row.stdout_log or "")
    assert fake.calls[0][0] == "http://mlops-runner:8020/run-pipeline"
    assert fake.calls[0][1] == {"Authorization": "Bearer shared"}


def test_execute_run_marks_failed_when_runner_url_missing(monkeypatch) -> None:
    monkeypatch.setenv("MLOPS_PIPELINE_ENABLED", "true")
    monkeypatch.delenv("MLOPS_RUNNER_URL", raising=False)

    db = MagicMock()
    row = MagicMock()
    row.status = "QUEUED"
    db.get.return_value = row

    service = MlopsOpsService(db, config=MlopsOpsConfig())
    import uuid

    service.execute_run(uuid.uuid4())
    assert row.status == "FAILED"
    assert "MLOPS_RUNNER_URL" in (row.stderr_log or "")
