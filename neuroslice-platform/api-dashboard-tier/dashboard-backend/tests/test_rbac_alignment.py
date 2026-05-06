from __future__ import annotations

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


def test_sessions_are_restricted_to_admin_and_noc() -> None:
    holder = {"principal": _principal("NETWORK_MANAGER")}

    def override_user() -> AuthenticatedPrincipal:
        return holder["principal"]

    app = main.app
    app.dependency_overrides[get_current_user] = override_user

    with TestClient(app) as client:
        holder["principal"] = _principal("NETWORK_MANAGER")
        manager_response = client.get("/sessions")
        assert manager_response.status_code == 403

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
        assert manager_write.status_code == 403

        holder["principal"] = _principal("DATA_MLOPS_ENGINEER")
        mlops_write = client.post("/controls/drift/trigger")
        assert mlops_write.status_code == 200

    app.dependency_overrides.clear()
