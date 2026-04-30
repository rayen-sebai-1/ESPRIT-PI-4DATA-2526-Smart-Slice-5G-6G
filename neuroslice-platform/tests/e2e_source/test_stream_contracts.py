from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _iter_source_files() -> list[Path]:
    allowed_suffixes = {".py", ".md", ".yml", ".yaml", ".json", ".ts", ".tsx"}
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in allowed_suffixes:
            continue
        files.append(path)
    return files


def _contains_token(token: str) -> bool:
    for path in _iter_source_files():
        try:
            if token in path.read_text(encoding="utf-8"):
                return True
        except UnicodeDecodeError:
            continue
    return False


def test_required_stream_names_exist_in_source_contracts() -> None:
    required_tokens = [
        "stream:raw.ves",
        "stream:raw.netconf",
        "stream:norm.telemetry",
        "events.anomaly",
        "events.sla",
        "events.slice.classification",
        "stream:control.alerts",
        "stream:control.actions",
        "events.drift",
        "events.evaluation",
    ]
    missing = [token for token in required_tokens if not _contains_token(token)]
    assert not missing, f"Missing stream contract tokens in source: {missing}"
