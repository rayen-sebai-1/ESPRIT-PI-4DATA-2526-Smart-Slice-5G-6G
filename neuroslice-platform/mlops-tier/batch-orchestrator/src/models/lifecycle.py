"""Shared helpers for MLflow tracking, artifact logging, and model promotion."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    import mlflow
except ModuleNotFoundError:
    class _MissingMlflow:
        @staticmethod
        def _raise(*args: Any, **kwargs: Any) -> None:
            raise ModuleNotFoundError("mlflow is required for tracking. Install requirements.txt first.")

        set_tracking_uri = _raise
        set_experiment = _raise
        start_run = _raise
        active_run = _raise
        log_artifact = _raise
        get_artifact_uri = _raise
        log_dict = _raise
        set_tag = _raise
        set_tags = _raise

    mlflow = _MissingMlflow()

from src.models.export_onnx import ONNXExportResult, export_model_to_onnx

ROOT_DIR = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT_DIR / "models"
ONNX_DIR = MODELS_DIR / "onnx"
REGISTRY_PATH = MODELS_DIR / "registry.json"
REPORT_PATH = ROOT_DIR / "reports" / "model_training_summary.md"
LOCAL_MLFLOW_DB = ROOT_DIR / "mlflow.db"
DEFAULT_LOCAL_TRACKING_URI = f"sqlite:///{LOCAL_MLFLOW_DB.resolve().as_posix()}"
DEFAULT_EXPERIMENT_NAME = "neuroslice-aiops"

DATASET_STATUS_PATHS = {
    "congestion_5g": ROOT_DIR / "data" / "processed" / "congestion_5g_processed.npz",
    "congestion_6g": ROOT_DIR / "data" / "processed" / "6g_processed.csv",
    "sla_5g": ROOT_DIR / "data" / "processed" / "sla_5g_processed.npz",
    "sla_6g": ROOT_DIR / "data" / "processed" / "sla_6g_processed.npz",
    "slice_type_5g": ROOT_DIR / "data" / "processed" / "slice_type_5g_processed.npz",
    "slice_type_6g": ROOT_DIR / "data" / "processed" / "slice_type_6g_processed.npz",
}

METRIC_ALIASES = {
    "val_accuracy": ("val_accuracy", "accuracy"),
    "val_precision": ("val_precision", "precision"),
    "val_recall": ("val_recall", "recall"),
    "val_f1": ("val_f1", "f1", "val_f1_score"),
    "val_roc_auc": ("val_roc_auc", "auc_roc", "val_auc"),
    "val_mae": ("val_mae", "final_val_mae", "mae"),
    "val_rmse": ("val_rmse", "final_val_rmse", "rmse"),
    "val_mape": ("val_mape", "final_val_mape", "mape"),
}

MODEL_SELECTION_RULES = {
    "congestion_5g": ("val_f1", "max"),
    "congestion_6g": ("val_mae", "min"),
    "sla_5g": ("val_roc_auc", "max"),
    "sla_6g": ("val_roc_auc", "max"),
    "slice_type_5g": ("val_accuracy", "max"),
    "slice_type_6g": ("val_accuracy", "max"),
}


def configure_mlflow_tracking() -> str:
    """Configure MLflow tracking from the environment with a local fallback."""
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI") or DEFAULT_LOCAL_TRACKING_URI
    mlflow.set_tracking_uri(tracking_uri)

    for name in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "MLFLOW_S3_ENDPOINT_URL",
    ):
        if os.getenv(name):
            os.environ[name] = str(os.getenv(name))

    return tracking_uri


def get_experiment_name(default: str = DEFAULT_EXPERIMENT_NAME) -> str:
    """Return the shared production experiment name."""
    return os.getenv("MLFLOW_EXPERIMENT_NAME", default)


def use_mlflow_experiment(experiment_name: str | None = None) -> str:
    """Create or select the shared MLflow experiment and return its name."""
    resolved_name = experiment_name or get_experiment_name()
    mlflow.set_experiment(resolved_name)
    return resolved_name


def finalize_model_lifecycle(
    *,
    model_name: str,
    model_family: str,
    artifact_format: str,
    metrics: Mapping[str, Any],
    local_artifact_path: Path | str | None,
    task_type: str = "classification",
    experiment_name: str | None = None,
    preprocessor_path: Path | str | None = None,
    input_schema: Mapping[str, Any] | None = None,
    model: Any | None = None,
    export_kind: str | None = None,
    export_basename: str | None = None,
    example_input: Any | None = None,
    input_names: Sequence[str] | None = None,
    output_names: Sequence[str] | None = None,
    dynamic_axes: Mapping[str, Mapping[int, str]] | None = None,
    run_smoke_test: bool | None = None,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    """Log artifacts, export ONNX/FP16 when possible, and update registry metadata."""
    normalized_metrics = normalize_metrics(metrics)
    active_run = mlflow.active_run()
    run_id = active_run.info.run_id if active_run else ""
    resolved_experiment = experiment_name or get_experiment_name()

    local_path = Path(local_artifact_path) if local_artifact_path else None
    preprocessor_local_path = Path(preprocessor_path) if preprocessor_path else None

    artifact_uri = _log_artifact_and_get_uri(local_path, "models")
    preprocessor_uri = _log_artifact_and_get_uri(preprocessor_local_path, "preprocessing")

    if export_kind and model is not None and example_input is not None and export_basename:
        onnx_result = export_model_to_onnx(
            model=model,
            export_kind=export_kind,
            output_basename=export_basename,
            example_input=example_input,
            output_dir=ONNX_DIR,
            input_names=input_names,
            output_names=output_names,
            dynamic_axes=dynamic_axes,
            run_smoke_test=_resolve_smoke_test_flag(run_smoke_test),
        )
    else:
        onnx_result = ONNXExportResult(
            status="failed",
            reason="ONNX export skipped because the export configuration is incomplete.",
        )

    onnx_uri = _log_artifact_and_get_uri(onnx_result.raw_path, "onnx")
    onnx_fp16_uri = _log_artifact_and_get_uri(onnx_result.fp16_path, "onnx")
    _record_onnx_export_status(model_name, onnx_result)

    selected_format = _select_artifact_format(
        requested_format=artifact_format,
        onnx_uri=onnx_uri,
        onnx_fp16_uri=onnx_fp16_uri,
    )
    decision = evaluate_promotion(model_name, normalized_metrics)
    combined_reason = _combine_reasons(decision["reason"], onnx_result)
    selection_metric, selection_mode = MODEL_SELECTION_RULES.get(model_name, ("val_accuracy", "max"))

    entry = {
        "model_name": model_name,
        "task_type": task_type,
        "version": 0,
        "stage": _initial_stage(decision),
        "promoted": False,
        "format": selected_format,
        "artifact_uri": artifact_uri,
        "onnx_uri": onnx_uri,
        "onnx_fp16_uri": onnx_fp16_uri,
        "preprocessor_uri": preprocessor_uri,
        "mlflow_run_id": run_id,
        "experiment_name": resolved_experiment,
        "metrics": normalized_metrics,
        "quality_gate_status": decision["quality_gate_status"],
        "input_schema": dict(input_schema or {}),
        "created_at": utcnow_iso(),
        "quality_gate_reason": combined_reason,
        "selection_metric": selection_metric,
        "selection_mode": selection_mode,
        "registered_model_family": model_family,
        "warnings": decision["warnings"],
        "onnx_export_status": onnx_result.status,
        "onnx_export_reason": onnx_result.reason,
        "onnx_smoke_test_passed": onnx_result.smoke_test_passed,
        # Backward-compatible aliases consumed by existing reports/loaders.
        "model_family": model_family,
        "run_id": run_id,
        "artifact_format": selected_format,
        "local_artifact_path": _to_registry_relative_path(local_path),
        "mlflow_artifact_uri": artifact_uri,
        "onnx_path": _to_registry_relative_path(onnx_result.raw_path),
        "onnx_fp16_path": _to_registry_relative_path(onnx_result.fp16_path),
        "preprocessor_path": _to_registry_relative_path(preprocessor_local_path),
        "promotion_status": decision["promotion_status"],
        "reason": combined_reason,
    }

    entry = write_registry_entry(entry, registry_path=registry_path or REGISTRY_PATH)

    mlflow.set_tags(
        {
            "neuroslice.model_name": model_name,
            "neuroslice.model_version": str(entry["version"]),
            "neuroslice.stage": entry["stage"],
            "neuroslice.promoted": str(entry["promoted"]).lower(),
            "neuroslice.quality_gate_status": entry["quality_gate_status"],
            "neuroslice.onnx_export_status": entry["onnx_export_status"],
            "neuroslice.artifact_format": entry["format"],
            "neuroslice.registry_path": str((registry_path or REGISTRY_PATH).as_posix()),
        }
    )
    return entry


def write_registry_entry(entry: Mapping[str, Any], *, registry_path: Path = REGISTRY_PATH) -> dict[str, Any]:
    """Append a registry entry and refresh production promotion for that model."""
    registry = load_registry(registry_path)
    model_name = str(entry["model_name"])
    version = _next_version(registry["models"], model_name)
    new_entry = dict(entry)
    new_entry["version"] = version
    registry["models"].append(new_entry)
    _refresh_promotions(registry["models"], model_name)
    registry["generated_at"] = utcnow_iso()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")

    for item in registry["models"]:
        if str(item.get("model_name")) == model_name and int(item.get("version", 0)) == version:
            return item
    return new_entry


def load_registry(registry_path: Path = REGISTRY_PATH) -> dict[str, Any]:
    """Load the registry JSON, creating a stable empty structure when missing."""
    if not registry_path.exists():
        return {"generated_at": None, "models": []}

    raw = json.loads(registry_path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return {"generated_at": None, "models": raw}
    return {"generated_at": raw.get("generated_at"), "models": list(raw.get("models", []))}


def latest_registry_entries(registry_path: Path = REGISTRY_PATH) -> list[dict[str, Any]]:
    """Return the latest entry for each model name."""
    latest: dict[str, dict[str, Any]] = {}
    for entry in load_registry(registry_path)["models"]:
        current = latest.get(str(entry.get("model_name")))
        if current is None or int(entry.get("version", 0)) >= int(current.get("version", 0)):
            latest[str(entry.get("model_name"))] = entry
    return sorted(latest.values(), key=lambda item: str(item.get("model_name", "")))


def normalize_metrics(metrics: Mapping[str, Any]) -> dict[str, float]:
    """Normalize metric names so registry rules can stay stable across scripts."""
    normalized = {str(key): float(value) for key, value in metrics.items() if _is_number(value)}

    for canonical_name, aliases in METRIC_ALIASES.items():
        if canonical_name in normalized:
            continue
        for alias in aliases:
            if alias in normalized:
                normalized[canonical_name] = float(normalized[alias])
                break
    return normalized


def evaluate_promotion(model_name: str, metrics: Mapping[str, Any]) -> dict[str, Any]:
    """Apply per-model promotion rules."""
    warnings: list[str] = []

    if model_name in {"sla_5g", "sla_6g"}:
        auc = float(metrics.get("val_roc_auc", 0.0))
        passed = auc >= 0.75
        return _decision(
            passed=passed,
            reason=f"val_roc_auc={auc:.4f} {'meets' if passed else 'does not meet'} the >= 0.75 rule.",
            failure_status="candidate",
            warnings=warnings,
        )

    if model_name == "slice_type_5g":
        accuracy = float(metrics.get("val_accuracy", 0.0))
        passed = accuracy >= 0.80
        return _decision(
            passed=passed,
            reason=f"val_accuracy={accuracy:.4f} {'meets' if passed else 'does not meet'} the >= 0.80 rule.",
            failure_status="candidate",
            warnings=warnings,
        )

    if model_name == "slice_type_6g":
        accuracy = float(metrics.get("val_accuracy", 0.0))
        passed = accuracy >= 0.80
        if accuracy == 1.0:
            warnings.append("Suspicious 100% validation accuracy detected; possible leakage.")
        return _decision(
            passed=passed,
            reason=f"val_accuracy={accuracy:.4f} {'meets' if passed else 'does not meet'} the >= 0.80 rule.",
            failure_status="candidate",
            warnings=warnings,
        )

    if model_name == "congestion_6g":
        mae = float(metrics.get("val_mae", float("inf")))
        passed = mae < 5.0
        return _decision(
            passed=passed,
            reason=f"val_mae={mae:.4f} {'meets' if passed else 'does not meet'} the < 5.0 rule.",
            failure_status="candidate",
            warnings=warnings,
        )

    if model_name == "congestion_5g":
        precision = float(metrics.get("val_precision", 0.0))
        recall = float(metrics.get("val_recall", 0.0))
        if precision >= 0.50 and recall >= 0.70:
            return {
                "quality_gate_status": "pass",
                "promotion_status": "promoted",
                "reason": (
                    f"val_precision={precision:.4f} and val_recall={recall:.4f} meet the "
                    "minimum precision >= 0.50 and recall >= 0.70 rule."
                ),
                "warnings": warnings,
            }
        if precision < 0.50:
            return {
                "quality_gate_status": "fail",
                "promotion_status": "rejected",
                "reason": (
                    f"val_precision={precision:.4f} is below 0.50; congestion_5g is not auto-promoted on AUC alone."
                ),
                "warnings": warnings,
            }
        return {
            "quality_gate_status": "fail",
            "promotion_status": "candidate",
            "reason": f"val_recall={recall:.4f} is below the 0.70 promotion threshold.",
            "warnings": warnings,
        }

    return {
        "quality_gate_status": "fail",
        "promotion_status": "candidate",
        "reason": "No promotion rule is defined for this model.",
        "warnings": warnings,
    }


def dataset_status() -> list[dict[str, str]]:
    """Return dataset-processing status for the report generator."""
    rows: list[dict[str, str]] = []
    for model_name, path in DATASET_STATUS_PATHS.items():
        try:
            display_path = path.relative_to(ROOT_DIR).as_posix()
        except ValueError:
            display_path = path.as_posix()
        rows.append(
            {
                "model_name": model_name,
                "status": "processed" if path.exists() else "missing",
                "path": display_path,
            }
        )
    return rows


def normalize_artifact_uri(uri: str | None) -> str:
    """Normalize proxied MLflow artifact URIs to the configured MinIO root when possible."""
    if not uri:
        return ""
    artifact_root = os.getenv("MLFLOW_ARTIFACT_ROOT", "").rstrip("/")
    if artifact_root.startswith("s3://") and uri.startswith("mlflow-artifacts:/"):
        suffix = uri[len("mlflow-artifacts:/") :].lstrip("/")
        return f"{artifact_root}/{suffix}" if suffix else artifact_root
    return uri


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _refresh_promotions(entries: list[dict[str, Any]], model_name: str) -> None:
    model_entries = [entry for entry in entries if str(entry.get("model_name")) == model_name]
    for entry in model_entries:
        entry["promoted"] = False
        if entry.get("quality_gate_status") == "pass":
            entry["stage"] = "staging"
            entry["promotion_status"] = "candidate"
        elif entry.get("promotion_status") == "rejected":
            entry["stage"] = "rejected"
        else:
            entry["stage"] = "candidate"

    candidates = [entry for entry in model_entries if entry.get("quality_gate_status") == "pass"]
    if not candidates:
        return

    best_entry = _best_entry_by_task_metric(model_name, candidates)
    best_entry["promoted"] = True
    best_entry["stage"] = "production"
    best_entry["promotion_status"] = "promoted"


def _best_entry_by_task_metric(model_name: str, candidates: Sequence[dict[str, Any]]) -> dict[str, Any]:
    metric_name, mode = MODEL_SELECTION_RULES.get(model_name, ("val_accuracy", "max"))
    reverse = mode == "max"
    missing_score = float("-inf") if reverse else float("inf")

    def sort_key(entry: dict[str, Any]) -> tuple[float, int]:
        metrics = entry.get("metrics") or {}
        score = float(metrics.get(metric_name, missing_score))
        if not reverse:
            score = -score
        return score, int(entry.get("version", 0))

    return max(candidates, key=sort_key)


def _log_artifact_and_get_uri(path: Path | None, artifact_path: str) -> str:
    if path is None or not path.exists():
        return ""
    mlflow.log_artifact(path.as_posix(), artifact_path=artifact_path)
    return normalize_artifact_uri(mlflow.get_artifact_uri(f"{artifact_path}/{path.name}"))


def _record_onnx_export_status(model_name: str, result: ONNXExportResult) -> None:
    status_payload = {
        "model_name": model_name,
        "status": result.status,
        "reason": result.reason,
        "raw_path": result.raw_path.as_posix() if result.raw_path else None,
        "fp16_path": result.fp16_path.as_posix() if result.fp16_path else None,
        "validated": result.validated,
        "smoke_test_passed": result.smoke_test_passed,
    }
    print(f"[INFO] ONNX export status for {model_name}: {result.status} - {result.reason}")
    mlflow.set_tag("neuroslice.onnx_export_status", result.status)
    mlflow.set_tag("neuroslice.onnx_export_reason", result.reason)
    mlflow.log_dict(status_payload, "reports/onnx_export_status.json")


def _select_artifact_format(*, requested_format: str, onnx_uri: str, onnx_fp16_uri: str) -> str:
    if onnx_fp16_uri:
        return "onnx_fp16"
    if onnx_uri:
        return "onnx"
    return requested_format


def _initial_stage(decision: Mapping[str, Any]) -> str:
    if decision.get("quality_gate_status") == "pass":
        return "staging"
    if decision.get("promotion_status") == "rejected":
        return "rejected"
    return "candidate"


def _resolve_smoke_test_flag(value: bool | None) -> bool:
    if value is not None:
        return value
    return os.getenv("ONNX_SMOKE_TEST", "").strip().lower() in {"1", "true", "yes", "on"}


def _combine_reasons(decision_reason: str, onnx_result: ONNXExportResult) -> str:
    parts = [decision_reason]
    if onnx_result.status != "success":
        parts.append(f"ONNX export failed: {onnx_result.reason}")
    return " ".join(part for part in parts if part).strip()


def _decision(*, passed: bool, reason: str, failure_status: str, warnings: list[str]) -> dict[str, Any]:
    return {
        "quality_gate_status": "pass" if passed else "fail",
        "promotion_status": "promoted" if passed else failure_status,
        "reason": reason,
        "warnings": warnings,
    }


def _next_version(entries: Sequence[Mapping[str, Any]], model_name: str) -> int:
    versions = [
        int(entry.get("version", 0))
        for entry in entries
        if str(entry.get("model_name")) == model_name
    ]
    return (max(versions) if versions else 0) + 1


def _to_registry_relative_path(path: Path | None) -> str | None:
    if path is None:
        return None
    resolved = path.resolve()
    if not resolved.exists():
        return None

    try:
        return resolved.relative_to(MODELS_DIR.resolve()).as_posix()
    except ValueError:
        try:
            return resolved.relative_to(ROOT_DIR.resolve()).as_posix()
        except ValueError:
            return resolved.as_posix()


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False
