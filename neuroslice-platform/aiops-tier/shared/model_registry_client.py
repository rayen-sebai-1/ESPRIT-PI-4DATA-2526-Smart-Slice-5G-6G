"""Scenario B registry reader for promoted offline models.

Local `registry.json` is the first integration target. Direct MLflow and MinIO
downloads are intentionally left as a TODO so the runtime can evolve without
breaking the existing local-mount workflow.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ModelRegistryClient:
    def __init__(self, *, registry_path: str | Path, tracking_uri: str | None = None) -> None:
        self.registry_path = Path(registry_path)
        self.tracking_uri = tracking_uri

    def load_registry(self) -> dict[str, Any]:
        if self.registry_path.exists():
            raw = json.loads(self.registry_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                return {"generated_at": None, "models": raw}
            return {
                "generated_at": raw.get("generated_at"),
                "models": list(raw.get("models", [])),
            }

        if self.tracking_uri:
            logger.info(
                "Model registry JSON not found at %s. TODO: add direct MLflow/MinIO download for %s.",
                self.registry_path,
                self.tracking_uri,
            )
        else:
            logger.info("Model registry JSON not found at %s.", self.registry_path)
        return {"generated_at": None, "models": []}

    def get_promoted_model(self, model_name: str) -> dict[str, Any] | None:
        entries = [
            entry
            for entry in self.load_registry()["models"]
            if str(entry.get("model_name")) == model_name
            and str(entry.get("promotion_status")) == "promoted"
        ]
        if not entries:
            return None
        return max(entries, key=lambda item: int(item.get("version", 0)))

    def get_promoted_model_version(self, model_name: str) -> str:
        entry = self.get_promoted_model(model_name)
        if not entry:
            return ""
        return str(entry.get("version", ""))

    def should_reload_model(
        self,
        current_version: str,
        model_name: str,
        *,
        preferred_format: str = "onnx_fp16",
    ) -> bool:
        promoted = self.get_promoted_model(model_name)
        if not promoted:
            return False

        if preferred_format == "onnx_fp16" and not promoted.get("onnx_fp16_path"):
            return False

        promoted_version = str(promoted.get("version", ""))
        return bool(promoted_version and promoted_version != str(current_version or ""))

    def resolve_artifact_path(
        self,
        entry: dict[str, Any],
        *,
        preferred_format: str = "onnx_fp16",
    ) -> Path | None:
        candidate_keys = []
        if preferred_format == "onnx_fp16":
            candidate_keys.append("onnx_fp16_path")
        candidate_keys.append("local_artifact_path")

        for key in candidate_keys:
            raw_path = entry.get(key)
            if not raw_path:
                continue
            resolved = self._resolve_path(raw_path)
            if resolved.exists():
                return resolved
        return None

    def _resolve_path(self, raw_path: str | Path) -> Path:
        path = Path(raw_path)
        if path.is_absolute():
            return path

        candidate = self.registry_path.parent / path
        if candidate.exists():
            return candidate.resolve()

        project_relative = self.registry_path.parent.parent / path
        if project_relative.exists():
            return project_relative.resolve()

        return candidate.resolve()
