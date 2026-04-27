from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

from schemas import (
    MlopsActionResponse,
    MlopsArtifactStatus,
    MlopsModelHealth,
    MlopsOverview,
    MlopsPredictionMonitoringPoint,
    MlopsPredictionMonitoringResponse,
    MlopsPromoteRequest,
    MlopsPromotedModel,
    MlopsPromotionEvent,
    MlopsRegistryEntry,
    MlopsRollbackRequest,
    MlopsRunSummary,
)

DEFAULT_MODELS_DIR = "/mlops/models"
DEFAULT_METRIC_KEYS = ("val_accuracy", "val_precision", "val_recall", "val_f1", "val_roc_auc")


class MlopsService:
    """Read-only and delegating facade over the MLOps platform.

    Reads model registry data, promoted artifact metadata, and optionally
    delegates promotion/rollback to MLOPS_API_BASE_URL. No MinIO secrets,
    DB credentials, or JWT secrets are ever sent back to the caller.
    """

    def __init__(
        self,
        *,
        models_dir: str | None = None,
        mlops_api_base_url: str | None = None,
        elasticsearch_url: str | None = None,
        elasticsearch_index: str | None = None,
        http_client_factory=None,
    ) -> None:
        self.models_dir = Path(models_dir or os.getenv("MLOPS_MODELS_DIR", DEFAULT_MODELS_DIR))
        self.mlops_api_base_url = (
            mlops_api_base_url
            if mlops_api_base_url is not None
            else os.getenv("MLOPS_API_BASE_URL")
        )
        self.elasticsearch_url = (
            elasticsearch_url
            if elasticsearch_url is not None
            else os.getenv("ES_HOST")
        )
        self.elasticsearch_index = (
            elasticsearch_index
            if elasticsearch_index is not None
            else os.getenv("ES_INDEX_NAME", "smart-slice-predictions")
        )
        self._http_client_factory = http_client_factory or (lambda: httpx.Client(timeout=5.0))

    # --- Filesystem helpers -------------------------------------------------

    def _registry_path(self) -> Path:
        return self.models_dir / "registry.json"

    def _promoted_root(self) -> Path:
        return self.models_dir / "promoted"

    def _safe_deployment_dir(self, deployment_name: str) -> Path | None:
        if not deployment_name or "/" in deployment_name or "\\" in deployment_name or ".." in deployment_name:
            return None
        candidate = (self._promoted_root() / deployment_name).resolve()
        try:
            candidate.relative_to(self._promoted_root().resolve())
        except (ValueError, FileNotFoundError):
            return None
        return candidate

    def _read_registry(self) -> dict[str, Any] | None:
        path = self._registry_path()
        if not path.is_file():
            return None
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        return data

    def _registry_models(self) -> list[dict[str, Any]]:
        registry = self._read_registry() or {}
        models = registry.get("models")
        if not isinstance(models, list):
            return []
        return [m for m in models if isinstance(m, dict)]

    def _list_promoted_dirs(self) -> list[Path]:
        root = self._promoted_root()
        if not root.is_dir():
            return []
        return sorted(p for p in root.iterdir() if p.is_dir())

    def _read_promoted_metadata(self, deployment_name: str) -> tuple[MlopsPromotedModel | None, list[str]]:
        deployment_dir = self._safe_deployment_dir(deployment_name)
        if deployment_dir is None:
            return None, []
        current = deployment_dir / "current"
        if not current.is_dir():
            return None, []

        metadata_path = current / "metadata.json"
        files: list[str] = []
        try:
            files = sorted(p.name for p in current.iterdir() if p.is_file())
        except OSError:
            files = []

        metadata: dict[str, Any] = {}
        if metadata_path.is_file():
            try:
                with metadata_path.open("r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                    if isinstance(loaded, dict):
                        metadata = loaded
            except (OSError, json.JSONDecodeError):
                metadata = {}

        promoted = MlopsPromotedModel(
            deployment_name=deployment_name,
            model_name=str(metadata.get("model_name")) if metadata.get("model_name") else None,
            version=(str(metadata["version"]) if metadata.get("version") is not None else None),
            framework=metadata.get("framework"),
            run_id=metadata.get("run_id"),
            updated_at=metadata.get("updated_at"),
            created_at=metadata.get("created_at"),
            metrics=_filter_metrics(metadata.get("metrics")),
            artifact_available=any(name.endswith(".onnx") for name in files),
            artifact_files=files,
        )
        return promoted, files

    # --- Public read APIs ---------------------------------------------------

    def get_overview(self) -> MlopsOverview:
        registry = self._read_registry()
        registry_models = self._registry_models()
        promoted_dirs = self._list_promoted_dirs()

        promoted_health: list[MlopsModelHealth] = []
        for directory in promoted_dirs:
            promoted, _files = self._read_promoted_metadata(directory.name)
            registry_entry = self._latest_registry_entry_for_deployment(directory.name, registry_models)
            promoted_health.append(
                _build_health(directory.name, promoted=promoted, registry=registry_entry)
            )

        pass_count = sum(1 for m in registry_models if m.get("quality_gate_status") == "pass")
        fail_count = sum(1 for m in registry_models if m.get("quality_gate_status") == "fail")
        pending = sum(
            1
            for m in registry_models
            if m.get("promotion_status") not in {"promoted", "rejected"}
        )

        return MlopsOverview(
            generated_at=(registry or {}).get("generated_at") if isinstance(registry, dict) else None,
            registry_available=registry is not None,
            promoted_models_count=len(promoted_dirs),
            models_with_pass_gate=pass_count,
            models_with_fail_gate=fail_count,
            pending_runs=pending,
            promoted_models=promoted_health,
            sources={
                "registry": "filesystem" if registry is not None else "unavailable",
                "mlops_api": "configured" if self.mlops_api_base_url else "disabled",
                "elasticsearch": "configured" if self.elasticsearch_url else "disabled",
            },
        )

    def list_models(self) -> list[MlopsModelHealth]:
        registry_models = self._registry_models()
        promoted_dirs = self._list_promoted_dirs()
        promoted_names = {p.name for p in promoted_dirs}

        seen: set[str] = set()
        result: list[MlopsModelHealth] = []

        for directory in promoted_dirs:
            promoted, _files = self._read_promoted_metadata(directory.name)
            registry_entry = self._latest_registry_entry_for_deployment(directory.name, registry_models)
            result.append(_build_health(directory.name, promoted=promoted, registry=registry_entry))
            seen.add(directory.name)

        deployment_groups: dict[str, list[dict[str, Any]]] = {}
        for entry in registry_models:
            name = str(entry.get("model_name") or "")
            if not name or name in promoted_names:
                continue
            deployment_groups.setdefault(name, []).append(entry)

        for name, entries in deployment_groups.items():
            if name in seen:
                continue
            latest = _select_latest(entries)
            registry_entry = _to_registry_entry(latest) if latest else None
            result.append(_build_health(name, promoted=None, registry=registry_entry))

        return result

    def get_model_detail(self, model_name: str) -> MlopsModelHealth | None:
        registry_models = self._registry_models()
        promoted_dirs = {p.name for p in self._list_promoted_dirs()}

        if model_name in promoted_dirs:
            promoted, _files = self._read_promoted_metadata(model_name)
            registry_entry = self._latest_registry_entry_for_deployment(model_name, registry_models)
            return _build_health(model_name, promoted=promoted, registry=registry_entry)

        matching = [m for m in registry_models if m.get("model_name") == model_name]
        if not matching:
            return None
        latest = _select_latest(matching)
        return _build_health(
            model_name,
            promoted=None,
            registry=_to_registry_entry(latest) if latest else None,
        )

    def list_runs(self, *, limit: int = 50) -> list[MlopsRunSummary]:
        models = self._registry_models()
        ordered = sorted(
            models,
            key=lambda m: str(m.get("created_at") or ""),
            reverse=True,
        )
        runs: list[MlopsRunSummary] = []
        for entry in ordered[: max(1, min(limit, 200))]:
            runs.append(
                MlopsRunSummary(
                    model_name=str(entry.get("model_name") or "unknown"),
                    version=entry.get("version"),
                    run_id=entry.get("run_id") or entry.get("mlflow_run_id"),
                    stage=entry.get("stage"),
                    quality_gate_status=entry.get("quality_gate_status"),
                    promotion_status=entry.get("promotion_status"),
                    created_at=entry.get("created_at"),
                    metrics=_filter_metrics(entry.get("metrics")),
                )
            )
        return runs

    def list_artifacts(self) -> list[MlopsArtifactStatus]:
        artifacts: list[MlopsArtifactStatus] = []
        for directory in self._list_promoted_dirs():
            current = directory / "current"
            files: list[str] = []
            if current.is_dir():
                try:
                    files = sorted(p.name for p in current.iterdir() if p.is_file())
                except OSError:
                    files = []
            artifacts.append(
                MlopsArtifactStatus(
                    deployment_name=directory.name,
                    has_metadata="metadata.json" in files,
                    has_onnx="model.onnx" in files,
                    has_onnx_fp16="model_fp16.onnx" in files,
                    files=files,
                )
            )
        return artifacts

    def list_promotions(self, *, limit: int = 50) -> list[MlopsPromotionEvent]:
        models = self._registry_models()
        ordered = sorted(
            models,
            key=lambda m: str(m.get("created_at") or ""),
            reverse=True,
        )
        events: list[MlopsPromotionEvent] = []
        for entry in ordered:
            status = entry.get("promotion_status")
            if status not in {"promoted", "rejected"}:
                continue
            events.append(
                MlopsPromotionEvent(
                    model_name=str(entry.get("model_name") or "unknown"),
                    version=entry.get("version"),
                    run_id=entry.get("run_id") or entry.get("mlflow_run_id"),
                    stage=entry.get("stage"),
                    promotion_status=status,
                    promoted=bool(entry.get("promoted")),
                    reason=entry.get("reason"),
                    created_at=entry.get("created_at"),
                )
            )
            if len(events) >= max(1, min(limit, 200)):
                break
        return events

    def get_prediction_monitoring(
        self,
        *,
        model: str | None = None,
        limit: int = 50,
    ) -> MlopsPredictionMonitoringResponse:
        if not self.elasticsearch_url:
            return MlopsPredictionMonitoringResponse(
                available=False,
                source="elasticsearch",
                total=0,
                items=[],
                note="Elasticsearch not configured (ES_HOST is empty).",
            )

        query: dict[str, Any] = {
            "size": max(1, min(limit, 200)),
            "sort": [{"@timestamp": {"order": "desc"}}],
        }
        if model:
            query["query"] = {"term": {"model.keyword": model}}

        try:
            with self._http_client_factory() as client:
                response = client.post(
                    f"{self.elasticsearch_url.rstrip('/')}/{self.elasticsearch_index}/_search",
                    json=query,
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            return MlopsPredictionMonitoringResponse(
                available=False,
                source="elasticsearch",
                total=0,
                items=[],
                note="Elasticsearch query failed.",
            )

        hits = (((payload or {}).get("hits") or {}).get("hits")) or []
        total_obj = ((payload or {}).get("hits") or {}).get("total") or {}
        total_value = total_obj.get("value") if isinstance(total_obj, dict) else len(hits)

        items: list[MlopsPredictionMonitoringPoint] = []
        for hit in hits:
            source = hit.get("_source") if isinstance(hit, dict) else {}
            if not isinstance(source, dict):
                continue
            items.append(
                MlopsPredictionMonitoringPoint(
                    timestamp=str(source.get("@timestamp") or source.get("timestamp") or ""),
                    model=source.get("model"),
                    region=source.get("region"),
                    risk_level=source.get("risk_level"),
                    sla_score=_to_float(source.get("sla_score")),
                )
            )

        return MlopsPredictionMonitoringResponse(
            available=True,
            source="elasticsearch",
            total=int(total_value or len(items)),
            items=items,
        )

    # --- Action APIs (delegate to MLOPS_API_BASE_URL) -----------------------

    def promote_model(self, payload: MlopsPromoteRequest) -> MlopsActionResponse:
        return self._delegate_action(
            action="promote",
            path="/promotions",
            json_payload=payload.model_dump(exclude_none=True),
            model_name=payload.model_name,
        )

    def rollback_model(self, payload: MlopsRollbackRequest) -> MlopsActionResponse:
        return self._delegate_action(
            action="rollback",
            path="/promotions/rollback",
            json_payload=payload.model_dump(exclude_none=True),
            model_name=payload.model_name,
        )

    def _delegate_action(
        self,
        *,
        action: str,
        path: str,
        json_payload: dict[str, Any],
        model_name: str,
    ) -> MlopsActionResponse:
        if not self.mlops_api_base_url:
            return MlopsActionResponse(
                accepted=False,
                action=action,
                model_name=model_name,
                detail="MLOPS_API_BASE_URL is not configured.",
                delegated_to=None,
            )
        try:
            with self._http_client_factory() as client:
                response = client.post(
                    f"{self.mlops_api_base_url.rstrip('/')}{path}",
                    json=json_payload,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            return MlopsActionResponse(
                accepted=False,
                action=action,
                model_name=model_name,
                detail=f"MLOps API call failed: {type(exc).__name__}",
                delegated_to=self.mlops_api_base_url,
            )

        return MlopsActionResponse(
            accepted=True,
            action=action,
            model_name=model_name,
            detail=f"{action} request accepted by MLOps API.",
            delegated_to=self.mlops_api_base_url,
        )

    # --- Helpers ------------------------------------------------------------

    def _latest_registry_entry_for_deployment(
        self,
        deployment_name: str,
        registry_models: list[dict[str, Any]],
    ) -> MlopsRegistryEntry | None:
        candidates = [
            m
            for m in registry_models
            if m.get("model_name") == deployment_name or _matches_deployment(m, deployment_name)
        ]
        latest = _select_latest(candidates)
        return _to_registry_entry(latest) if latest else None


def _matches_deployment(entry: dict[str, Any], deployment_name: str) -> bool:
    deployed_name = entry.get("deployment_name")
    if isinstance(deployed_name, str) and deployed_name == deployment_name:
        return True
    promoted = entry.get("promoted_current_metadata_path")
    if isinstance(promoted, str) and f"/{deployment_name}/" in promoted:
        return True
    return False


def _select_latest(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not entries:
        return None
    promoted = [e for e in entries if e.get("stage") == "production" or e.get("promoted")]
    if promoted:
        return sorted(promoted, key=lambda e: str(e.get("created_at") or ""), reverse=True)[0]
    return sorted(entries, key=lambda e: str(e.get("created_at") or ""), reverse=True)[0]


def _to_registry_entry(entry: dict[str, Any]) -> MlopsRegistryEntry:
    return MlopsRegistryEntry(
        model_name=str(entry.get("model_name") or "unknown"),
        version=entry.get("version"),
        stage=entry.get("stage"),
        promoted=bool(entry.get("promoted")),
        framework=entry.get("framework") or entry.get("model_family"),
        model_family=entry.get("model_family"),
        quality_gate_status=entry.get("quality_gate_status"),
        promotion_status=entry.get("promotion_status"),
        onnx_export_status=entry.get("onnx_export_status"),
        created_at=entry.get("created_at"),
        run_id=entry.get("run_id") or entry.get("mlflow_run_id"),
        metrics=_filter_metrics(entry.get("metrics")),
        reason=entry.get("reason"),
    )


def _filter_metrics(metrics: Any) -> dict[str, float]:
    if not isinstance(metrics, dict):
        return {}
    cleaned: dict[str, float] = {}
    for key, value in metrics.items():
        try:
            cleaned[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return cleaned


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_health(
    deployment_name: str,
    *,
    promoted: MlopsPromotedModel | None,
    registry: MlopsRegistryEntry | None,
) -> MlopsModelHealth:
    notes: list[str] = []
    health: str = "unknown"

    if promoted is not None:
        if promoted.artifact_available:
            health = "healthy"
        else:
            health = "degraded"
            notes.append("Promoted directory missing ONNX artifact.")

    if registry is not None:
        gate = registry.quality_gate_status
        if gate == "fail":
            health = "degraded"
            notes.append("Latest run failed quality gate.")
        elif gate == "pass" and health == "unknown":
            health = "healthy"

    return MlopsModelHealth(
        deployment_name=deployment_name,
        promoted=promoted,
        registry=registry,
        health=health,  # type: ignore[arg-type]
        notes=notes,
    )


def get_mlops_service() -> MlopsService:
    return MlopsService()
