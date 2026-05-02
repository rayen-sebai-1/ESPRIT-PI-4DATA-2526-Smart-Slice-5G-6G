"""Production model promotion and deployment artifact materialization."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import unquote, urlparse

ROOT_DIR = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT_DIR / "models"
PROMOTED_DIR = MODELS_DIR / "promoted"
DEFAULT_REGISTERED_MODEL_NAMES = {
    "congestion_5g": "congestion-lstm-5g",
    "sla_5g": "sla-xgboost-5g",
    "slice_type_5g": "slice-type-lgbm-5g",
}
DEFAULT_DEPLOYMENT_FRAMEWORKS = {
    "congestion_5g": "pytorch",
    "sla_5g": "xgboost",
    "slice_type_5g": "lightgbm",
}


@dataclass(frozen=True)
class PromotionResult:
    """Paths and metadata produced for one promoted model version."""

    model_name: str
    version: str
    raw_path: Path
    fp16_path: Path
    current_raw_path: Path
    current_fp16_path: Path
    metadata_path: Path
    current_metadata_path: Path
    metadata: dict[str, Any]


def convert_onnx_to_fp16(
    source_path: Path | str,
    target_path: Path | str,
    *,
    keep_fp32_io: bool = True,
) -> Path:
    """Convert a float32 ONNX model to FP16 using onnxconverter-common."""
    import onnx
    from onnxconverter_common import float16

    source = Path(source_path)
    target = Path(target_path)
    if not source.exists():
        raise FileNotFoundError(f"ONNX source file does not exist: {source}")

    target.parent.mkdir(parents=True, exist_ok=True)
    model_proto = onnx.load(source.as_posix())
    fp16_model = float16.convert_float_to_float16(
        model_proto, keep_io_types=keep_fp32_io
    )
    onnx.save_model(fp16_model, target.as_posix())
    return target


def convert_to_fp16(model_path: Path | str, output_path: Path | str) -> Path:
    """Compatibility wrapper for the production FP16 conversion API."""
    import onnx
    from onnxconverter_common import float16

    source = Path(model_path)
    target = Path(output_path)
    if not source.exists():
        raise FileNotFoundError(f"ONNX source file does not exist: {source}")

    target.parent.mkdir(parents=True, exist_ok=True)
    model = onnx.load(source.as_posix())
    model_fp16 = float16.convert_float_to_float16(model)
    onnx.save(model_fp16, target.as_posix())
    return target


def promote_model(
    *,
    model_name: str,
    run_id: str,
    onnx_path: Path | str,
    fp16_path: Path | str | None = None,
    version: str | int | None = None,
    metrics: Mapping[str, Any] | None = None,
    framework: str | None = None,
    registered_model_name: str | None = None,
    promoted_root: Path | str = PROMOTED_DIR,
) -> PromotionResult:
    """Promote one exported ONNX model to the local production folder."""
    resolved_registered_name = (
        registered_model_name or DEFAULT_REGISTERED_MODEL_NAMES.get(model_name)
    )
    resolved_version = (
        str(version)
        if version not in {None, ""}
        else latest_registered_model_version(resolved_registered_name, run_id=run_id)
    )
    if not resolved_version:
        resolved_version = _next_promoted_version(
            model_name, promoted_root=promoted_root
        )

    return promote_onnx_artifacts(
        model_name=model_name,
        version=resolved_version,
        run_id=run_id,
        metrics=dict(metrics or {}),
        framework=framework
        or DEFAULT_DEPLOYMENT_FRAMEWORKS.get(model_name, infer_framework(model_name)),
        raw_onnx_path=onnx_path,
        fp16_onnx_path=fp16_path,
        promoted_root=promoted_root,
        registered_model_name=resolved_registered_name,
    )


def promote_onnx_artifacts(
    *,
    model_name: str,
    version: str | int,
    run_id: str,
    metrics: Mapping[str, Any],
    framework: str,
    raw_onnx_path: Path | str,
    fp16_onnx_path: Path | str | None = None,
    promoted_root: Path | str = PROMOTED_DIR,
    created_at: str | None = None,
    updated_at: str | None = None,
    registered_model_name: str | None = None,
    keep_fp32_io: bool = True,
) -> PromotionResult:
    """Copy ONNX artifacts into versioned and current production locations.

    The current pointer is updated only after raw ONNX, FP16 ONNX, and ONNX
    Runtime load checks pass for the versioned artifacts.
    """
    version_str = str(version)
    root = Path(promoted_root)
    version_dir = root / model_name / version_str
    current_dir = root / model_name / "current"
    version_dir.mkdir(parents=True, exist_ok=True)
    current_dir.mkdir(parents=True, exist_ok=True)

    source_raw = Path(raw_onnx_path)
    if not source_raw.exists():
        raise FileNotFoundError(f"Raw ONNX file does not exist: {source_raw}")

    version_raw = version_dir / "model.onnx"
    version_fp16 = version_dir / "model_fp16.onnx"
    _copy_if_different(source_raw, version_raw)

    if fp16_onnx_path and Path(fp16_onnx_path).exists():
        _copy_if_different(Path(fp16_onnx_path), version_fp16)
    else:
        convert_onnx_to_fp16(version_raw, version_fp16, keep_fp32_io=keep_fp32_io)

    validate_promoted_artifacts(version_raw, version_fp16)

    current_raw = current_dir / "model.onnx"
    current_fp16 = current_dir / "model_fp16.onnx"
    _copy_if_different(version_raw, current_raw)
    _copy_if_different(version_fp16, current_fp16)

    timestamp = updated_at or utcnow_iso()
    metadata = {
        "model_name": registered_model_name or model_name,
        "deployment_name": model_name,
        "version": version_str,
        "run_id": str(run_id or ""),
        "updated_at": timestamp,
        "metrics": _json_safe_metrics(metrics),
        "created_at": created_at or timestamp,
        "framework": normalize_framework(framework),
    }

    version_metadata = version_dir / "metadata.json"
    current_metadata = current_dir / "metadata.json"
    _write_json_atomic(version_metadata, metadata)
    _write_json_atomic(current_metadata, metadata)
    _write_text_atomic(current_dir / "version.txt", version_str)

    result = PromotionResult(
        model_name=model_name,
        version=version_str,
        raw_path=version_raw,
        fp16_path=version_fp16,
        current_raw_path=current_raw,
        current_fp16_path=current_fp16,
        metadata_path=version_metadata,
        current_metadata_path=current_metadata,
        metadata=metadata,
    )

    # Generate drift reference artifacts alongside the promoted model.
    # Failure is non-fatal: the drift-monitor handles reference_missing gracefully.
    try:
        from mlops.drift_reference import generate_drift_reference

        drift_result = generate_drift_reference(
            model_name=model_name,
            current_dir=current_dir,
        )
        if drift_result.get("status") == "ok":
            import logging as _logging

            _logging.getLogger(__name__).info(
                "[%s] Drift reference generated: n_samples=%s",
                model_name,
                drift_result.get("n_samples"),
            )
        else:
            import logging as _logging

            _logging.getLogger(__name__).warning(
                "[%s] Drift reference not generated: %s",
                model_name,
                drift_result.get("status"),
            )
    except Exception as _exc:  # noqa: BLE001
        import logging as _logging

        _logging.getLogger(__name__).warning(
            "[%s] Drift reference generation failed (non-fatal): %s", model_name, _exc
        )

    return result


def validate_promoted_artifacts(
    raw_onnx_path: Path | str, fp16_onnx_path: Path | str
) -> None:
    """Verify promoted ONNX artifacts exist, are structurally valid, and load in ORT."""
    import onnx
    import onnxruntime as ort

    raw_path = Path(raw_onnx_path)
    fp16_path = Path(fp16_onnx_path)
    if not raw_path.exists():
        raise FileNotFoundError(f"Promoted raw ONNX file does not exist: {raw_path}")
    if not fp16_path.exists():
        raise FileNotFoundError(f"Promoted FP16 ONNX file does not exist: {fp16_path}")

    onnx.checker.check_model(onnx.load(raw_path.as_posix()))
    onnx.checker.check_model(onnx.load(fp16_path.as_posix()))
    ort.InferenceSession(fp16_path.as_posix(), providers=["CPUExecutionProvider"])


def latest_registered_model_version(
    registered_model_name: str | None,
    *,
    run_id: str | None = None,
) -> str | None:
    """Return the latest MLflow registered model version, preferring the active run."""
    if not registered_model_name:
        return None

    try:
        from mlflow.tracking import MlflowClient

        client = MlflowClient()
        versions = list(
            client.search_model_versions(f"name = '{registered_model_name}'")
        )
    except Exception:  # noqa: BLE001
        return None

    if run_id:
        run_versions = [
            item for item in versions if str(getattr(item, "run_id", "")) == str(run_id)
        ]
        if run_versions:
            versions = run_versions

    if not versions:
        return None

    latest = max(versions, key=lambda item: int(getattr(item, "version", 0)))
    return str(getattr(latest, "version", ""))


def materialize_promoted_model_for_registry(
    *,
    model_name: str,
    registry_path: Path | str,
) -> dict[str, Any] | None:
    """Refresh the promoted/current deployment folder for the production registry entry."""
    registry_file = Path(registry_path)
    registry = _load_registry(registry_file)
    models_dir = registry_file.parent.resolve()
    promoted_root = models_dir / "promoted"

    model_entries = [
        entry
        for entry in registry["models"]
        if str(entry.get("model_name")) == model_name
    ]
    production_entries = [
        entry
        for entry in model_entries
        if bool(entry.get("promoted"))
        or str(entry.get("stage", "")).lower() == "production"
    ]
    if not production_entries:
        return None

    successful_entries = [
        entry
        for entry in production_entries
        if str(entry.get("onnx_export_status", "")).lower() == "success"
    ]
    selected_entry = max(
        successful_entries or production_entries,
        key=lambda item: int(item.get("version", 0)),
    )

    raw_onnx = _resolve_onnx_artifact(selected_entry, models_dir=models_dir, fp16=False)
    fp16_onnx = _resolve_onnx_artifact(selected_entry, models_dir=models_dir, fp16=True)
    if raw_onnx is None or not raw_onnx.exists():
        selected_entry["promoted_artifact_status"] = "missing_onnx_artifact"
        _write_registry(registry_file, registry)
        return selected_entry

    deployment_version = str(
        selected_entry.get("deployment_version") or selected_entry.get("version") or ""
    )
    if not deployment_version:
        selected_entry["promoted_artifact_status"] = "missing_version"
        _write_registry(registry_file, registry)
        return selected_entry

    try:
        result = promote_onnx_artifacts(
            model_name=model_name,
            version=deployment_version,
            run_id=str(
                selected_entry.get("mlflow_run_id")
                or selected_entry.get("run_id")
                or ""
            ),
            metrics=dict(selected_entry.get("metrics") or {}),
            framework=selected_entry.get("framework")
            or infer_framework(selected_entry),
            raw_onnx_path=raw_onnx,
            fp16_onnx_path=fp16_onnx,
            promoted_root=promoted_root,
            created_at=str(selected_entry.get("created_at") or utcnow_iso()),
            updated_at=utcnow_iso(),
            registered_model_name=str(selected_entry.get("registered_model_name") or "")
            or None,
        )
    except Exception as exc:  # noqa: BLE001
        selected_entry["promoted_artifact_status"] = "validation_failed"
        selected_entry["promoted_artifact_reason"] = str(exc)
        _write_registry(registry_file, registry)
        raise

    selected_entry["deployment_version"] = deployment_version
    selected_entry["promoted_artifact_status"] = "ready"
    selected_entry["promoted_onnx_path"] = _to_registry_relative_path(
        result.raw_path, models_dir=models_dir
    )
    selected_entry["promoted_fp16_path"] = _to_registry_relative_path(
        result.fp16_path, models_dir=models_dir
    )
    selected_entry["promoted_current_onnx_path"] = _to_registry_relative_path(
        result.current_raw_path,
        models_dir=models_dir,
    )
    selected_entry["promoted_current_fp16_path"] = _to_registry_relative_path(
        result.current_fp16_path,
        models_dir=models_dir,
    )
    selected_entry["promoted_metadata_path"] = _to_registry_relative_path(
        result.metadata_path, models_dir=models_dir
    )
    selected_entry["promoted_current_metadata_path"] = _to_registry_relative_path(
        result.current_metadata_path,
        models_dir=models_dir,
    )

    registry["generated_at"] = utcnow_iso()
    _write_registry(registry_file, registry)
    return selected_entry


def infer_framework(entry_or_name: Mapping[str, Any] | str | None) -> str:
    """Normalize a model family/export kind to the deployment framework label."""
    if isinstance(entry_or_name, Mapping):
        for key in (
            "framework",
            "export_kind",
            "registered_model_family",
            "model_family",
        ):
            value = entry_or_name.get(key)
            if value:
                return normalize_framework(str(value))
        return "unknown"
    return normalize_framework(str(entry_or_name or ""))


def normalize_framework(value: str) -> str:
    lowered = value.strip().lower()
    if "torch" in lowered or "pytorch" in lowered or "lstm" in lowered:
        return "pytorch"
    if "xgb" in lowered or "xgboost" in lowered:
        return "xgboost"
    if "lgbm" in lowered or "lightgbm" in lowered:
        return "lightgbm"
    if lowered in {"pytorch", "xgboost", "lightgbm"}:
        return lowered
    return lowered or "unknown"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _resolve_onnx_artifact(
    entry: Mapping[str, Any], *, models_dir: Path, fp16: bool
) -> Path | None:
    keys = (
        (
            "promoted_current_fp16_path",
            "promoted_fp16_path",
            "onnx_fp16_path",
            "onnx_fp16_uri",
        )
        if fp16
        else (
            "promoted_current_onnx_path",
            "promoted_onnx_path",
            "onnx_path",
            "onnx_uri",
        )
    )
    for key in keys:
        resolved = _resolve_local_reference(entry.get(key), models_dir=models_dir)
        if resolved is not None and resolved.exists():
            return resolved
    return None


def _resolve_local_reference(raw_value: Any, *, models_dir: Path) -> Path | None:
    if not raw_value:
        return None

    value = str(raw_value)
    parsed = urlparse(value)

    if parsed.scheme in {"", None}:
        candidate = Path(value)
        if candidate.is_absolute():
            return candidate.resolve()

        local_candidate = (models_dir / candidate).resolve()
        if local_candidate.exists():
            return local_candidate

        repo_candidate = (models_dir.parent / candidate).resolve()
        if repo_candidate.exists():
            return repo_candidate

        return local_candidate

    if parsed.scheme == "file":
        return Path(unquote(parsed.path)).resolve()

    basename = Path(parsed.path).name
    if not basename:
        return None

    for root in (models_dir / "onnx", models_dir, models_dir / "promoted"):
        candidate = (root / basename).resolve()
        if candidate.exists():
            return candidate
    return None


def _load_registry(registry_path: Path) -> dict[str, Any]:
    if not registry_path.exists():
        return {"generated_at": None, "models": []}

    raw = json.loads(registry_path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return {"generated_at": None, "models": raw}
    return {
        "generated_at": raw.get("generated_at"),
        "models": list(raw.get("models", [])),
    }


def _write_registry(registry_path: Path, registry: Mapping[str, Any]) -> None:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(registry_path, registry)


def _to_registry_relative_path(path: Path | None, *, models_dir: Path) -> str | None:
    if path is None:
        return None
    resolved = path.resolve()
    if not resolved.exists():
        return None

    try:
        return resolved.relative_to(models_dir.resolve()).as_posix()
    except ValueError:
        try:
            return resolved.relative_to(models_dir.parent.resolve()).as_posix()
        except ValueError:
            return resolved.as_posix()


def _copy_if_different(source: Path, destination: Path) -> None:
    source_resolved = source.resolve()
    destination_resolved = (
        destination.resolve() if destination.exists() else destination
    )
    if source_resolved == destination_resolved:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_resolved, destination)


def _next_promoted_version(model_name: str, *, promoted_root: Path | str) -> str:
    model_dir = Path(promoted_root) / model_name
    if not model_dir.exists():
        return "1"

    versions = [
        int(path.name)
        for path in model_dir.iterdir()
        if path.is_dir() and path.name.isdigit()
    ]
    return str((max(versions) if versions else 0) + 1)


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _write_text_atomic(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(path)


def _json_safe_metrics(metrics: Mapping[str, Any]) -> dict[str, float]:
    safe: dict[str, float] = {}
    for key, value in metrics.items():
        try:
            safe[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return safe
