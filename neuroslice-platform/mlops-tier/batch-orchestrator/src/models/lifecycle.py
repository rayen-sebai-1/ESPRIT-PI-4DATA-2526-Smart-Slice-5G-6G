"""Shared helpers for the offline model lifecycle and registry metadata."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import mlflow

from src.models.export_onnx import ONNXExportResult, export_model_to_onnx

ROOT_DIR = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT_DIR / "models"
ONNX_DIR = MODELS_DIR / "onnx"
REGISTRY_PATH = MODELS_DIR / "registry.json"
REPORT_PATH = ROOT_DIR / "reports" / "model_training_summary.md"
LOCAL_MLFLOW_DB = ROOT_DIR / "mlflow.db"
DEFAULT_LOCAL_TRACKING_URI = f"sqlite:///{LOCAL_MLFLOW_DB.resolve().as_posix()}"

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


def configure_mlflow_tracking() -> str:
    """Configure MLflow tracking with a local fallback."""
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


def finalize_model_lifecycle(
    *,
    model_name: str,
    model_family: str,
    artifact_format: str,
    metrics: Mapping[str, Any],
    local_artifact_path: Path | str | None,
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
    """Write registry metadata and attach Scenario B artifacts to the active run."""
    normalized_metrics = normalize_metrics(metrics)
    active_run = mlflow.active_run()
    run_id = active_run.info.run_id if active_run else ""

    local_path = Path(local_artifact_path) if local_artifact_path else None
    if local_path and local_path.exists():
        mlflow.log_artifact(local_path.as_posix(), artifact_path="offline_artifacts")

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

    mlflow_artifact_uri = _artifact_uri_for_result(onnx_result=onnx_result, local_path=local_path, run_id=run_id)

    if onnx_result.fp16_path and onnx_result.fp16_path.exists():
        mlflow.log_artifact(onnx_result.fp16_path.as_posix(), artifact_path="onnx")
        mlflow_artifact_uri = mlflow.get_artifact_uri(f"onnx/{onnx_result.fp16_path.name}")

    decision = evaluate_promotion(model_name, normalized_metrics)
    combined_reason = _combine_reasons(decision["reason"], onnx_result)

    entry = {
        "model_name": model_name,
        "model_family": model_family,
        "version": 0,
        "created_at": utcnow_iso(),
        "run_id": run_id,
        "metrics": normalized_metrics,
        "quality_gate_status": decision["quality_gate_status"],
        "artifact_format": "onnx_fp16" if onnx_result.status == "success" else artifact_format,
        "local_artifact_path": _to_registry_relative_path(local_path),
        "mlflow_artifact_uri": mlflow_artifact_uri,
        "onnx_fp16_path": _to_registry_relative_path(onnx_result.fp16_path),
        "onnx_export_status": onnx_result.status,
        "promotion_status": decision["promotion_status"],
        "reason": combined_reason,
        "warnings": decision["warnings"],
        "onnx_export_reason": onnx_result.reason,
    }

    entry = write_registry_entry(entry, registry_path=registry_path or REGISTRY_PATH)

    mlflow.set_tags(
        {
            "scenario_b.model_name": model_name,
            "scenario_b.model_version": str(entry["version"]),
            "scenario_b.quality_gate_status": entry["quality_gate_status"],
            "scenario_b.promotion_status": entry["promotion_status"],
            "scenario_b.onnx_export_status": entry["onnx_export_status"],
            "scenario_b.artifact_format": entry["artifact_format"],
        }
    )
    return entry


def write_registry_entry(entry: Mapping[str, Any], *, registry_path: Path = REGISTRY_PATH) -> dict[str, Any]:
    """Append a registry entry and assign a monotonically increasing version."""
    registry = load_registry(registry_path)
    version = _next_version(registry["models"], str(entry["model_name"]))
    new_entry = dict(entry)
    new_entry["version"] = version
    registry["generated_at"] = utcnow_iso()
    registry["models"].append(new_entry)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
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
    """Apply per-model promotion rules for Scenario B."""
    warnings: list[str] = []

    if model_name == "sla_5g":
        auc = float(metrics.get("val_roc_auc", 0.0))
        passed = auc >= 0.75
        return _decision(
            passed=passed,
            reason=f"val_roc_auc={auc:.4f} {'meets' if passed else 'does not meet'} the >= 0.75 rule.",
            failure_status="candidate",
            warnings=warnings,
        )

    if model_name == "sla_6g":
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


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _resolve_smoke_test_flag(value: bool | None) -> bool:
    if value is not None:
        return value
    return os.getenv("ONNX_SMOKE_TEST", "").strip().lower() in {"1", "true", "yes", "on"}


def _artifact_uri_for_result(*, onnx_result: ONNXExportResult, local_path: Path | None, run_id: str) -> str:
    if onnx_result.fp16_path and onnx_result.fp16_path.exists():
        return mlflow.get_artifact_uri(f"onnx/{onnx_result.fp16_path.name}")
    if local_path and local_path.exists():
        return mlflow.get_artifact_uri(f"offline_artifacts/{local_path.name}")
    if run_id and mlflow.active_run():
        return mlflow.active_run().info.artifact_uri
    return ""


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
