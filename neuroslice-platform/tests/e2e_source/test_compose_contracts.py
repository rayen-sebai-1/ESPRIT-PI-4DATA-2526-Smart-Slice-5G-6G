from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = ROOT / "infrastructure" / "docker-compose.yml"
KONG_PATH = ROOT / "api-dashboard-tier" / "kong-gateway" / "kong.yml"


def _services_from_compose(compose_text: str) -> set[str]:
    services_block = compose_text.split("services:", 1)[1].split("\nvolumes:", 1)[0]
    return set(re.findall(r"^  ([a-z0-9-]+):\s*$", services_block, flags=re.MULTILINE))


def test_required_services_exist() -> None:
    text = COMPOSE_PATH.read_text(encoding="utf-8")
    services = _services_from_compose(text)

    required = {
        "congestion-detector",
        "sla-assurance",
        "slice-classifier",
        "aiops-drift-monitor",
        "online-evaluator",
        "alert-management",
        "policy-control",
        "mlops-runner",
        "mlops-drift-monitor",
        "dashboard-backend",
        "api-bff-service",
        "kong-gateway",
        "react-dashboard",
        "prometheus",
        "grafana",
    }
    missing = sorted(required - services)
    assert not missing, f"Missing required Compose services: {missing}"


def test_aiops_model_mounts_exist() -> None:
    text = COMPOSE_PATH.read_text(encoding="utf-8")
    assert "../mlops-tier/batch-orchestrator/models:/mlops/models:ro" in text
    assert "../mlops-tier/batch-orchestrator/data:/mlops/data:ro" in text


def test_kong_routes_include_dashboard_contracts() -> None:
    text = KONG_PATH.read_text(encoding="utf-8")
    for path in [
        "/api/dashboard/mlops",
        "/api/dashboard/controls",
        "/api/dashboard/agentic",
        "/api/dashboard/sessions",
        "/api/dashboard/predictions",
        "/api/dashboard/runtime",
    ]:
        assert path in text, f"Expected Kong route path not found: {path}"


def test_profiles_exist() -> None:
    text = COMPOSE_PATH.read_text(encoding="utf-8")
    assert 'profiles: ["mlops"]' in text
    assert 'profiles: ["drift"]' in text
    assert 'profiles: ["mlops-worker"]' in text
