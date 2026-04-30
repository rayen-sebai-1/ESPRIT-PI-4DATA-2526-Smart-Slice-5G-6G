from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PLATFORM_ROOT = Path(__file__).resolve().parents[2]

README_PATHS = [
    REPO_ROOT / "README.md",
    PLATFORM_ROOT / "README.md",
    PLATFORM_ROOT / "aiops-tier" / "README.md",
    PLATFORM_ROOT / "api-dashboard-tier" / "README.md",
    PLATFORM_ROOT / "mlops-tier" / "README.md",
    PLATFORM_ROOT / "infrastructure" / "README.md",
]


def _docs_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in README_PATHS if path.exists())


def test_readmes_do_not_claim_misrouting_detector_is_active() -> None:
    docs = _docs_text().lower()
    assert "misrouting-detector is active" not in docs
    assert "misrouting detector is active" not in docs


def test_readmes_state_agentic_scope_exclusion() -> None:
    docs = _docs_text().lower()
    assert "agentic" in docs
    assert (
        "out of current" in docs
        or "out of scope in the current" in docs
        or "excluded from current" in docs
    )


def test_drift_monitor_names_are_consistent() -> None:
    docs = _docs_text()
    assert "aiops-drift-monitor" in docs
    assert "mlops-drift-monitor" in docs


def test_no_obsolete_api_agentic_bypass_claims() -> None:
    docs = _docs_text()
    assert "/api/agentic/" not in docs
