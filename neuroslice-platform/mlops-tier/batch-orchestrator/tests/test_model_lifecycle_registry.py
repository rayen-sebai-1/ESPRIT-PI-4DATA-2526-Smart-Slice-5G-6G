"""Tests for registry metadata, MLflow artifact logging, and promotion rules."""

from src.models.export_onnx import ONNXExportResult
from src.models.lifecycle import (
    evaluate_promotion,
    finalize_model_lifecycle,
    load_registry,
    normalize_artifact_uri,
    write_registry_entry,
)


def _entry(model_name: str) -> dict:
    return {
        "model_name": model_name,
        "model_family": "test_family",
        "version": 0,
        "created_at": "2026-04-24T00:00:00+00:00",
        "run_id": "run-123",
        "metrics": {"val_accuracy": 0.9},
        "quality_gate_status": "pass",
        "artifact_format": "onnx_fp16",
        "local_artifact_path": "model.pkl",
        "mlflow_artifact_uri": "mlflow-artifacts:/model.pkl",
        "onnx_fp16_path": "onnx/model_fp16.onnx",
        "onnx_export_status": "success",
        "promotion_status": "promoted",
        "reason": "ok",
        "warnings": [],
        "onnx_export_reason": "ok",
    }


def test_write_registry_entry_increments_versions(tmp_path):
    registry_path = tmp_path / "registry.json"

    first = write_registry_entry(_entry("sla_5g"), registry_path=registry_path)
    second = write_registry_entry(_entry("sla_5g"), registry_path=registry_path)

    registry = load_registry(registry_path)

    assert first["version"] == 1
    assert second["version"] == 2
    assert len(registry["models"]) == 2


def test_write_registry_entry_keeps_only_best_passing_model_in_production(tmp_path):
    registry_path = tmp_path / "registry.json"

    older = _entry("sla_5g")
    older["metrics"] = {"val_roc_auc": 0.91}
    newer = _entry("sla_5g")
    newer["metrics"] = {"val_roc_auc": 0.82}

    write_registry_entry(older, registry_path=registry_path)
    write_registry_entry(newer, registry_path=registry_path)

    entries = load_registry(registry_path)["models"]
    production_entries = [entry for entry in entries if entry.get("stage") == "production"]

    assert len(production_entries) == 1
    assert production_entries[0]["version"] == 1
    assert production_entries[0]["promoted"] is True


def test_normalize_artifact_uri_maps_mlflow_proxy_to_minio_root(monkeypatch):
    monkeypatch.setenv("MLFLOW_ARTIFACT_ROOT", "s3://mlflow-artifacts")

    uri = normalize_artifact_uri("mlflow-artifacts:/1/run-123/artifacts/onnx/model_fp16.onnx")

    assert uri == "s3://mlflow-artifacts/1/run-123/artifacts/onnx/model_fp16.onnx"


def test_finalize_model_lifecycle_logs_artifacts_and_records_onnx_failure(tmp_path, monkeypatch):
    artifact_path = tmp_path / "model.pkl"
    artifact_path.write_text("model", encoding="utf-8")
    preprocessor_path = tmp_path / "preprocessor.pkl"
    preprocessor_path.write_text("preprocessor", encoding="utf-8")
    registry_path = tmp_path / "registry.json"

    logged_artifacts = []
    logged_dicts = []

    class _RunInfo:
        run_id = "run-123"

    class _Run:
        info = _RunInfo()

    monkeypatch.setenv("MLFLOW_ARTIFACT_ROOT", "s3://mlflow-artifacts")
    monkeypatch.setattr("src.models.lifecycle.mlflow.active_run", lambda: _Run())
    monkeypatch.setattr(
        "src.models.lifecycle.mlflow.log_artifact",
        lambda path, artifact_path=None: logged_artifacts.append((path, artifact_path)),
    )
    monkeypatch.setattr(
        "src.models.lifecycle.mlflow.get_artifact_uri",
        lambda path="": f"mlflow-artifacts:/1/run-123/artifacts/{path}",
    )
    monkeypatch.setattr("src.models.lifecycle.mlflow.set_tags", lambda tags: None)
    monkeypatch.setattr("src.models.lifecycle.mlflow.set_tag", lambda key, value: None)
    monkeypatch.setattr(
        "src.models.lifecycle.mlflow.log_dict",
        lambda payload, artifact_file: logged_dicts.append((payload, artifact_file)),
    )
    monkeypatch.setattr(
        "src.models.lifecycle.export_model_to_onnx",
        lambda **kwargs: ONNXExportResult(status="failed", reason="converter unavailable"),
    )

    entry = finalize_model_lifecycle(
        model_name="slice_type_5g",
        model_family="lightgbm_classifier",
        artifact_format="lightgbm_joblib",
        metrics={"val_accuracy": 0.91},
        local_artifact_path=artifact_path,
        task_type="multiclass_classification",
        experiment_name="neuroslice-aiops",
        preprocessor_path=preprocessor_path,
        input_schema={"features": ["a"], "shape": [None, 1]},
        model=object(),
        export_kind="lightgbm",
        export_basename="slice_type_5g",
        example_input=[[1.0]],
        registry_path=registry_path,
    )

    assert entry["quality_gate_status"] == "pass"
    assert entry["stage"] == "production"
    assert entry["promoted"] is True
    assert entry["format"] == "lightgbm_joblib"
    assert entry["artifact_uri"].startswith("s3://mlflow-artifacts/")
    assert entry["preprocessor_uri"].startswith("s3://mlflow-artifacts/")
    assert entry["onnx_export_status"] == "failed"
    assert "converter unavailable" in entry["onnx_export_reason"]
    assert ("reports/onnx_export_status.json" in [item[1] for item in logged_dicts])
    assert len(logged_artifacts) == 2


def test_sla_5g_promotion_rule_promotes_on_auc():
    decision = evaluate_promotion("sla_5g", {"val_roc_auc": 0.81})

    assert decision["quality_gate_status"] == "pass"
    assert decision["promotion_status"] == "promoted"


def test_congestion_5g_rejects_low_precision():
    decision = evaluate_promotion("congestion_5g", {"val_precision": 0.42, "val_recall": 0.82})

    assert decision["quality_gate_status"] == "fail"
    assert decision["promotion_status"] == "rejected"
    assert "below 0.50" in decision["reason"]


def test_slice_type_6g_perfect_accuracy_adds_warning():
    decision = evaluate_promotion("slice_type_6g", {"val_accuracy": 1.0})

    assert decision["quality_gate_status"] == "pass"
    assert decision["promotion_status"] == "promoted"
    assert decision["warnings"]
    assert "possible leakage" in decision["warnings"][0]
