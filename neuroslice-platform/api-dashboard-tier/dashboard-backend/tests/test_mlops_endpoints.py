from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
from mlops import MlopsService
from schemas import AuthenticatedPrincipal
from service import get_current_user


def _principal(role: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        id=1,
        session_id="00000000-0000-0000-0000-000000000000",
        full_name="Test User",
        email="test@neuroslice.tn",
        role=role,
        is_active=True,
    )


@pytest.fixture
def client(models_dir: Path):
    app = main.app

    def override_service():
        return MlopsService(
            models_dir=str(models_dir),
            mlops_api_base_url=None,
            elasticsearch_url=None,
        )

    app.dependency_overrides[main.get_mlops_service] = override_service

    holder: dict[str, AuthenticatedPrincipal] = {"principal": _principal("ADMIN")}

    def override_user():
        return holder["principal"]

    app.dependency_overrides[get_current_user] = override_user

    with TestClient(app) as test_client:
        yield test_client, holder

    app.dependency_overrides.clear()


def test_overview_admin_ok(client):
    test_client, _ = client
    response = test_client.get("/mlops/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["registry_available"] is True
    assert body["promoted_models_count"] == 1


def test_overview_data_mlops_engineer_ok(client):
    test_client, holder = client
    holder["principal"] = _principal("DATA_MLOPS_ENGINEER")
    response = test_client.get("/mlops/overview")
    assert response.status_code == 200


def test_overview_network_manager_read_only(client):
    test_client, holder = client
    holder["principal"] = _principal("NETWORK_MANAGER")
    response = test_client.get("/mlops/overview")
    assert response.status_code == 200


def test_overview_network_operator_forbidden(client):
    test_client, holder = client
    holder["principal"] = _principal("NETWORK_OPERATOR")
    response = test_client.get("/mlops/overview")
    assert response.status_code == 403


def test_promote_requires_writer_role(client):
    test_client, holder = client

    holder["principal"] = _principal("NETWORK_OPERATOR")
    forbidden = test_client.post("/mlops/promote", json={"model_name": "sla_5g"})
    assert forbidden.status_code == 403

    holder["principal"] = _principal("NETWORK_MANAGER")
    manager_response = test_client.post("/mlops/promote", json={"model_name": "sla_5g"})
    assert manager_response.status_code == 200

    holder["principal"] = _principal("DATA_MLOPS_ENGINEER")
    engineer_response = test_client.post("/mlops/promote", json={"model_name": "sla_5g"})
    assert engineer_response.status_code == 200
    body = engineer_response.json()
    assert body["accepted"] is False
    assert "MLOPS_API_BASE_URL" in body["detail"]


def test_rollback_requires_writer_role(client):
    test_client, holder = client

    holder["principal"] = _principal("NETWORK_OPERATOR")
    forbidden = test_client.post("/mlops/rollback", json={"model_name": "sla_5g"})
    assert forbidden.status_code == 403

    holder["principal"] = _principal("NETWORK_MANAGER")
    manager_response = test_client.post("/mlops/rollback", json={"model_name": "sla_5g"})
    assert manager_response.status_code == 200


def test_models_listing(client):
    test_client, _ = client
    response = test_client.get("/mlops/models")
    assert response.status_code == 200
    deployments = {entry["deployment_name"] for entry in response.json()}
    assert "sla_5g" in deployments


def test_model_detail_404(client):
    test_client, _ = client
    response = test_client.get("/mlops/models/does-not-exist")
    assert response.status_code == 404


def test_runs_artifacts_promotions(client):
    test_client, _ = client
    runs = test_client.get("/mlops/runs?limit=10")
    artifacts = test_client.get("/mlops/artifacts")
    promotions = test_client.get("/mlops/promotions?limit=10")
    assert runs.status_code == 200
    assert artifacts.status_code == 200
    assert promotions.status_code == 200
    assert len(runs.json()) >= 1
    assert len(artifacts.json()) == 1


def test_monitoring_disabled_safely(client):
    test_client, _ = client
    response = test_client.get("/mlops/monitoring/predictions")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["source"] == "elasticsearch"
