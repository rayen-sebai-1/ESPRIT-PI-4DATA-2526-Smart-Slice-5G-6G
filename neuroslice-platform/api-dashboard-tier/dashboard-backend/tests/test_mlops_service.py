from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from mlops import MlopsService
from schemas import MlopsPromoteRequest, MlopsRollbackRequest


class _FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            from httpx import HTTPStatusError, Request, Response

            raise HTTPStatusError(
                "boom",
                request=Request("POST", "http://test"),
                response=Response(self.status_code),
            )

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self, response: _FakeResponse):
        self.response = response
        self.calls: list[tuple[str, dict]] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url: str, json: dict | None = None):
        self.calls.append((url, json or {}))
        return self.response


@contextmanager
def _factory(client: _FakeClient):
    yield client


def test_overview_reads_filesystem(models_dir: Path) -> None:
    service = MlopsService(models_dir=str(models_dir), mlops_api_base_url=None, elasticsearch_url=None)
    overview = service.get_overview()

    assert overview.registry_available is True
    assert overview.promoted_models_count == 1
    assert overview.models_with_pass_gate == 1
    assert overview.models_with_fail_gate == 1
    assert overview.sources["registry"] == "filesystem"
    assert overview.sources["mlops_api"] == "disabled"
    assert any(model.deployment_name == "sla_5g" for model in overview.promoted_models)


def test_list_models_includes_registry_only_entries(models_dir: Path) -> None:
    service = MlopsService(models_dir=str(models_dir), mlops_api_base_url=None, elasticsearch_url=None)
    models = service.list_models()

    deployments = {m.deployment_name for m in models}
    assert {"sla_5g", "congestion_5g"}.issubset(deployments)

    sla = next(m for m in models if m.deployment_name == "sla_5g")
    assert sla.health == "healthy"
    assert sla.promoted is not None
    assert sla.promoted.artifact_available is True

    congestion = next(m for m in models if m.deployment_name == "congestion_5g")
    assert congestion.health == "degraded"
    assert congestion.promoted is None


def test_get_model_detail_unknown(models_dir: Path) -> None:
    service = MlopsService(models_dir=str(models_dir), mlops_api_base_url=None, elasticsearch_url=None)
    assert service.get_model_detail("does-not-exist") is None


def test_artifacts_and_promotions(models_dir: Path) -> None:
    service = MlopsService(models_dir=str(models_dir), mlops_api_base_url=None, elasticsearch_url=None)
    artifacts = service.list_artifacts()
    assert len(artifacts) == 1
    assert artifacts[0].deployment_name == "sla_5g"
    assert artifacts[0].has_metadata is True
    assert artifacts[0].has_onnx is True
    assert artifacts[0].has_onnx_fp16 is True

    promotions = service.list_promotions()
    statuses = {p.promotion_status for p in promotions}
    assert statuses == {"promoted", "rejected"}


def test_runs_sorted_desc(models_dir: Path) -> None:
    service = MlopsService(models_dir=str(models_dir), mlops_api_base_url=None, elasticsearch_url=None)
    runs = service.list_runs(limit=10)
    assert runs[0].model_name == "sla_5g"
    assert runs[-1].model_name == "congestion_5g"


def test_path_traversal_protection(models_dir: Path) -> None:
    service = MlopsService(models_dir=str(models_dir), mlops_api_base_url=None, elasticsearch_url=None)
    promoted, files = service._read_promoted_metadata("../../etc")
    assert promoted is None
    assert files == []


def test_promote_without_mlops_api_returns_unaccepted(models_dir: Path) -> None:
    service = MlopsService(models_dir=str(models_dir), mlops_api_base_url=None, elasticsearch_url=None)
    response = service.promote_model(MlopsPromoteRequest(model_name="sla_5g"))
    assert response.accepted is False
    assert "MLOPS_API_BASE_URL" in response.detail


def test_promote_delegates_to_mlops_api(models_dir: Path) -> None:
    fake = _FakeClient(_FakeResponse(200, {"ok": True}))
    service = MlopsService(
        models_dir=str(models_dir),
        mlops_api_base_url="http://mlops-api:8010",
        elasticsearch_url=None,
        http_client_factory=lambda: fake,
    )
    response = service.promote_model(MlopsPromoteRequest(model_name="sla_5g", version=2))
    assert response.accepted is True
    assert response.delegated_to == "http://mlops-api:8010"
    assert fake.calls[0][0].endswith("/promotions")
    assert fake.calls[0][1]["model_name"] == "sla_5g"


def test_rollback_handles_http_failure(models_dir: Path) -> None:
    fake = _FakeClient(_FakeResponse(500, {}))
    service = MlopsService(
        models_dir=str(models_dir),
        mlops_api_base_url="http://mlops-api:8010",
        elasticsearch_url=None,
        http_client_factory=lambda: fake,
    )
    response = service.rollback_model(MlopsRollbackRequest(model_name="sla_5g"))
    assert response.accepted is False
    assert response.delegated_to == "http://mlops-api:8010"


def test_prediction_monitoring_disabled_without_es(models_dir: Path) -> None:
    service = MlopsService(models_dir=str(models_dir), mlops_api_base_url=None, elasticsearch_url=None)
    monitoring = service.get_prediction_monitoring()
    assert monitoring.available is False
    assert monitoring.source == "elasticsearch"
    assert monitoring.note is not None


def test_prediction_monitoring_uses_es(models_dir: Path) -> None:
    fake = _FakeClient(
        _FakeResponse(
            200,
            {
                "hits": {
                    "total": {"value": 1},
                    "hits": [
                        {
                            "_source": {
                                "@timestamp": "2026-04-27T11:00:00Z",
                                "model": "sla_5g",
                                "region": "TN-01",
                                "risk_level": "LOW",
                                "sla_score": 0.97,
                            }
                        }
                    ],
                }
            },
        )
    )
    service = MlopsService(
        models_dir=str(models_dir),
        mlops_api_base_url=None,
        elasticsearch_url="http://elasticsearch:9200",
        http_client_factory=lambda: fake,
    )
    monitoring = service.get_prediction_monitoring(model="sla_5g", limit=10)
    assert monitoring.available is True
    assert monitoring.total == 1
    assert monitoring.items[0].model == "sla_5g"
    assert monitoring.items[0].sla_score == 0.97
