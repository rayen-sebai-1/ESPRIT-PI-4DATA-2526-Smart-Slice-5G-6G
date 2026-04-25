"""Registry reader for promoted offline models used by runtime AIOps services."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

logger = logging.getLogger(__name__)


class ModelRegistryClient:
    def __init__(
        self,
        *,
        registry_path: str | Path,
        tracking_uri: str | None = None,
        artifact_cache_dir: str | Path | None = None,
    ) -> None:
        self.registry_path = Path(registry_path)
        self.tracking_uri = tracking_uri
        self.artifact_cache_dir = Path(
            artifact_cache_dir or os.getenv("MODEL_ARTIFACT_CACHE_DIR", "/tmp/neuroslice-model-artifacts")
        )

    def load_registry(self) -> dict[str, Any]:
        if self.registry_path.exists():
            raw = json.loads(self.registry_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                return {"generated_at": None, "models": raw}
            return {
                "generated_at": raw.get("generated_at"),
                "models": list(raw.get("models", [])),
            }

        logger.info("Model registry JSON not found at %s.", self.registry_path)
        return {"generated_at": None, "models": []}

    def get_promoted_model(self, model_name: str) -> dict[str, Any] | None:
        entries = [
            entry
            for entry in self.load_registry()["models"]
            if str(entry.get("model_name")) == model_name and self._is_promoted(entry)
        ]
        if not entries:
            return None
        return max(entries, key=lambda item: (self._production_rank(item), int(item.get("version", 0))))

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

        if preferred_format == "onnx_fp16" and not self.has_artifact(promoted, preferred_format=preferred_format):
            return False

        promoted_version = str(promoted.get("version", ""))
        return bool(promoted_version and promoted_version != str(current_version or ""))

    def has_artifact(self, entry: dict[str, Any], *, preferred_format: str = "onnx_fp16") -> bool:
        return any(entry.get(key) for key in self._candidate_keys(preferred_format))

    def resolve_artifact_path(
        self,
        entry: dict[str, Any],
        *,
        preferred_format: str = "onnx_fp16",
    ) -> Path | None:
        for key in self._candidate_keys(preferred_format):
            raw_value = entry.get(key)
            if not raw_value:
                continue
            resolved = self._resolve_reference(str(raw_value))
            if resolved is not None and resolved.exists():
                return resolved
        return None

    def _resolve_reference(self, raw_value: str) -> Path | None:
        parsed = urlparse(raw_value)
        if parsed.scheme in {"", None}:
            return self._resolve_path(raw_value)

        if parsed.scheme == "file":
            return Path(unquote(parsed.path)).resolve()

        local_from_uri = self._resolve_uri_to_local_mount(raw_value)
        if local_from_uri is not None and local_from_uri.exists():
            return local_from_uri

        return self._download_artifact(raw_value)

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

    def _resolve_uri_to_local_mount(self, uri: str) -> Path | None:
        parsed = urlparse(uri)
        basename = Path(parsed.path).name
        if not basename:
            return None

        search_roots = [
            self.registry_path.parent,
            self.registry_path.parent / "onnx",
            self.registry_path.parent.parent,
            self.registry_path.parent.parent / "data" / "processed",
        ]
        for root in search_roots:
            candidate = root / basename
            if candidate.exists():
                return candidate.resolve()

        if "/onnx/" in parsed.path:
            candidate = self.registry_path.parent / "onnx" / basename
            return candidate.resolve()
        return None

    def _download_artifact(self, uri: str) -> Path | None:
        if not self.tracking_uri:
            logger.info("Cannot download model artifact %s because no MLflow tracking URI is configured.", uri)
            return None

        try:
            import mlflow

            mlflow.set_tracking_uri(self.tracking_uri)
            self.artifact_cache_dir.mkdir(parents=True, exist_ok=True)
            downloaded = mlflow.artifacts.download_artifacts(
                artifact_uri=uri,
                dst_path=self.artifact_cache_dir.as_posix(),
            )
            return Path(downloaded).resolve()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not download model artifact %s: %s", uri, exc)
            return None

    @staticmethod
    def _candidate_keys(preferred_format: str) -> list[str]:
        if preferred_format == "onnx_fp16":
            return [
                "onnx_fp16_path",
                "onnx_fp16_uri",
                "onnx_path",
                "onnx_uri",
                "local_artifact_path",
                "artifact_uri",
            ]
        if preferred_format == "onnx":
            return [
                "onnx_path",
                "onnx_uri",
                "onnx_fp16_path",
                "onnx_fp16_uri",
                "local_artifact_path",
                "artifact_uri",
            ]
        return ["local_artifact_path", "artifact_uri", "onnx_fp16_path", "onnx_fp16_uri", "onnx_path", "onnx_uri"]

    @staticmethod
    def _is_promoted(entry: dict[str, Any]) -> bool:
        if bool(entry.get("promoted")):
            return True
        if str(entry.get("stage", "")).lower() == "production":
            return True
        return str(entry.get("promotion_status", "")).lower() == "promoted"

    @staticmethod
    def _production_rank(entry: dict[str, Any]) -> int:
        return 1 if str(entry.get("stage", "")).lower() == "production" else 0
