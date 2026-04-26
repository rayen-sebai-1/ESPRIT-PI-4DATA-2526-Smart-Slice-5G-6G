"""Shared promoted-model metadata polling helpers for AIOps services."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PromotedModelSnapshot:
    model_path: Path
    metadata_path: Path
    metadata: dict[str, Any]
    version: str
    model_mtime_ns: int
    metadata_mtime_ns: int


def promoted_current_paths(registry_path: str | Path, model_name: str) -> tuple[Path, Path]:
    models_dir = Path(registry_path).expanduser().resolve().parent
    current_dir = models_dir / "promoted" / model_name / "current"
    return current_dir / "model_fp16.onnx", current_dir / "metadata.json"


def current_promoted_snapshot(registry_path: str | Path, model_name: str) -> PromotedModelSnapshot | None:
    model_path, metadata_path = promoted_current_paths(registry_path, model_name)
    if not model_path.exists() or not metadata_path.exists():
        return None

    metadata = read_promoted_metadata(metadata_path)
    version = str(metadata.get("version", "") or "")
    return PromotedModelSnapshot(
        model_path=model_path,
        metadata_path=metadata_path,
        metadata=metadata,
        version=version,
        model_mtime_ns=model_path.stat().st_mtime_ns,
        metadata_mtime_ns=metadata_path.stat().st_mtime_ns,
    )


def should_reload_promoted_model(
    *,
    registry_path: str | Path,
    model_name: str,
    current_version: str,
    current_model_source: str,
    current_metadata_mtime_ns: int = 0,
    current_model_mtime_ns: int = 0,
) -> bool:
    """Return true when promoted/current metadata or model bytes changed."""
    snapshot = current_promoted_snapshot(registry_path, model_name)
    if snapshot is None:
        return False

    if _normalize_path(current_model_source) != snapshot.model_path.resolve().as_posix():
        return True
    if snapshot.version and snapshot.version != str(current_version or ""):
        return True
    if current_metadata_mtime_ns and snapshot.metadata_mtime_ns != current_metadata_mtime_ns:
        return True
    if current_model_mtime_ns and snapshot.model_mtime_ns != current_model_mtime_ns:
        return True
    return False


def read_promoted_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalize_path(value: str) -> str:
    if not value:
        return ""
    try:
        return Path(value).expanduser().resolve().as_posix()
    except OSError:
        return value
