from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_MAIN = ROOT / "api-dashboard-tier" / "dashboard-backend" / "main.py"


def test_dashboard_backend_routes_include_required_contracts() -> None:
    text = DASHBOARD_MAIN.read_text(encoding="utf-8")

    required_routes = [
        "/mlops/pipeline/config",
        "/mlops/pipeline/run",
        "/controls/actions",
        "/runtime/services",
        "/mlops/evaluation",
    ]
    missing = [route for route in required_routes if route not in text]
    assert not missing, f"Missing dashboard-backend route contracts: {missing}"
