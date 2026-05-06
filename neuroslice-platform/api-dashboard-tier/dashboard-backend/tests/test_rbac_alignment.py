from __future__ import annotations

from datetime import UTC, datetime

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import main
from schemas import AuthenticatedPrincipal
from service import get_current_user


def _principal(role: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        id=1,
        session_id="00000000-0000-0000-0000-000000000000",
        full_name="RBAC Tester",
        email="rbac@neuroslice.tn",
        role=role,
        is_active=True,
    )


def test_mlops_can_read_dashboard() -> None:
    holder = {"principal": _principal("DATA_MLOPS_ENGINEER")}

    def override_user() -> AuthenticatedPrincipal:
        return holder["principal"]

    app = main.app
    app.dependency_overrides[get_current_user] = override_user

    with TestClient(app) as client:
        response = client.get("/dashboard/national")
        assert response.status_code == 200

    app.dependency_overrides.clear()


def test_sessions_are_available_to_manager_admin_and_noc() -> None:
    holder = {"principal": _principal("NETWORK_MANAGER")}

    def override_user() -> AuthenticatedPrincipal:
        return holder["principal"]

    app = main.app
    app.dependency_overrides[get_current_user] = override_user

    with TestClient(app) as client:
        holder["principal"] = _principal("NETWORK_MANAGER")
        manager_response = client.get("/sessions")
        assert manager_response.status_code == 200

        holder["principal"] = _principal("DATA_MLOPS_ENGINEER")
        mlops_response = client.get("/sessions")
        assert mlops_response.status_code == 403

        holder["principal"] = _principal("NETWORK_OPERATOR")
        noc_response = client.get("/sessions")
        assert noc_response.status_code == 200

    app.dependency_overrides.clear()


def test_prediction_run_is_admin_only() -> None:
    holder = {"principal": _principal("NETWORK_OPERATOR")}

    def override_user() -> AuthenticatedPrincipal:
        return holder["principal"]

    app = main.app
    app.dependency_overrides[get_current_user] = override_user

    with TestClient(app) as client:
        holder["principal"] = _principal("NETWORK_OPERATOR")
        noc_response = client.post("/predictions/run/1")
        assert noc_response.status_code == 403

        holder["principal"] = _principal("ADMIN")
        admin_response = client.post("/predictions/run/1")
        assert admin_response.status_code != 403

    app.dependency_overrides.clear()


def test_drift_read_write_roles_are_split(monkeypatch) -> None:
    holder = {"principal": _principal("ADMIN")}

    def override_user() -> AuthenticatedPrincipal:
        return holder["principal"]

    def fake_proxy_get(_: str):
        return JSONResponse({"ok": True})

    def fake_proxy_post(_: str, body: dict | None = None):
        _ = body
        return JSONResponse({"triggered": True})

    app = main.app
    app.dependency_overrides[get_current_user] = override_user
    monkeypatch.setattr(main, "_proxy_get", fake_proxy_get)
    monkeypatch.setattr(main, "_proxy_post", fake_proxy_post)

    with TestClient(app) as client:
        holder["principal"] = _principal("NETWORK_OPERATOR")
        noc_read = client.get("/controls/drift/status")
        assert noc_read.status_code == 200

        holder["principal"] = _principal("DATA_MLOPS_ENGINEER")
        mlops_read = client.get("/controls/drift/events")
        assert mlops_read.status_code == 200

        holder["principal"] = _principal("NETWORK_MANAGER")
        manager_write = client.post("/controls/drift/trigger")
        assert manager_write.status_code == 200

        holder["principal"] = _principal("DATA_MLOPS_ENGINEER")
        mlops_write = client.post("/controls/drift/trigger")
        assert mlops_write.status_code == 200

    app.dependency_overrides.clear()


def test_pipeline_run_is_role_based_not_account_bound() -> None:
    holder = {"principal": _principal("NETWORK_MANAGER")}

    def override_user() -> AuthenticatedPrincipal:
        return holder["principal"]

    class _FakeOpsConfig:
        pipeline_enabled = True

    class _FakeRun:
        id = "00000000-0000-0000-0000-000000000111"

    class _FakeOps:
        config = _FakeOpsConfig()

        @staticmethod
        def create_run(_: AuthenticatedPrincipal) -> _FakeRun:
            return _FakeRun()

        @staticmethod
        def _to_run_response(_: _FakeRun) -> dict:
            return {
                "run_id": "00000000-0000-0000-0000-000000000111",
                "triggered_by_user_id": 1,
                "triggered_by_email": "rbac@neuroslice.tn",
                "status": "QUEUED",
                "command_label": "full_pipeline",
                "started_at": None,
                "finished_at": None,
                "exit_code": None,
                "duration_seconds": None,
                "created_at": datetime.now(UTC),
            }

    app = main.app
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[main.get_mlops_ops_service] = lambda: _FakeOps()

    with TestClient(app) as client:
        holder["principal"] = _principal("NETWORK_MANAGER")
        manager_response = client.post("/mlops/pipeline/run")
        assert manager_response.status_code == 202

        holder["principal"] = _principal("DATA_MLOPS_ENGINEER")
        mlops_response = client.post("/mlops/pipeline/run")
        assert mlops_response.status_code == 202

        holder["principal"] = _principal("NETWORK_OPERATOR")
        operator_response = client.post("/mlops/pipeline/run")
        assert operator_response.status_code == 403
        assert operator_response.json().get("detail") == "Access denied."

    app.dependency_overrides.clear()


def test_agentic_roles_root_cause_and_copilot_are_split() -> None:
    holder = {"principal": _principal("DATA_MLOPS_ENGINEER")}

    def override_user() -> AuthenticatedPrincipal:
        return holder["principal"]

    class _FakeHttpxResponse:
        status_code = 200
        content = b'{"ok":true}'
        headers = {"content-type": "application/json"}

    class _FakeHttpxClient:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            _ = args, kwargs

        def __enter__(self) -> "_FakeHttpxClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
            return False

        def post(self, url: str, json: dict | None = None) -> _FakeHttpxResponse:
            _ = url, json
            return _FakeHttpxResponse()

        def get(self, url: str) -> _FakeHttpxResponse:
            _ = url
            return _FakeHttpxResponse()

    app = main.app
    app.dependency_overrides[get_current_user] = override_user
    old_httpx_client = main.httpx.Client
    main.httpx.Client = _FakeHttpxClient

    try:
        with TestClient(app) as client:
            holder["principal"] = _principal("DATA_MLOPS_ENGINEER")
            root_cause_response = client.post("/agentic/root-cause/manual-scan", json={"slice_id": "slice-1"})
            assert root_cause_response.status_code == 403
            assert root_cause_response.json().get("detail") == "Access denied."

            holder["principal"] = _principal("DATA_MLOPS_ENGINEER")
            copilot_response = client.post("/agentic/copilot/query/text", json={"session_id": "s1", "query": "status"})
            assert copilot_response.status_code == 200

            holder["principal"] = _principal("NETWORK_OPERATOR")
            noc_root_cause = client.post("/agentic/root-cause/manual-scan", json={"slice_id": "slice-1"})
            assert noc_root_cause.status_code == 200
    finally:
        main.httpx.Client = old_httpx_client
        app.dependency_overrides.clear()
