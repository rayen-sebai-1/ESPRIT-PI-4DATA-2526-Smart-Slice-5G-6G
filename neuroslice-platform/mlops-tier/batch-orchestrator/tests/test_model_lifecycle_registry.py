"""Tests for registry metadata, MLflow artifact logging, and promotion rules."""

import json

from src.models.export_onnx import ONNXExportResult
from src.models.lifecycle import (
    evaluate_promotion,
    finalize_model_lifecycle,
    load_registry,
    normalize_artifact_uri,
    write_registry_entry,
)
from src.mlops.promotion import convert_to_fp16, materialize_promoted_model_for_registry, promote_onnx_artifacts


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


def test_finalize_model_lifecycle_materializes_promoted_current_artifacts(tmp_path, monkeypatch):
    models_dir = tmp_path / "models"
    models_dir.mkdir(parents=True)
    onnx_dir = models_dir / "onnx"
    onnx_dir.mkdir(parents=True)

    raw_onnx = onnx_dir / "sla_5g.onnx"
    fp16_onnx = onnx_dir / "sla_5g_fp16.onnx"
    raw_onnx.write_text("raw", encoding="utf-8")
    fp16_onnx.write_text("fp16", encoding="utf-8")

    artifact_path = tmp_path / "sla_5g_model.ubj"
    artifact_path.write_text("model", encoding="utf-8")
    preprocessor_path = tmp_path / "scaler.pkl"
    preprocessor_path.write_text("preprocessor", encoding="utf-8")
    registry_path = models_dir / "registry.json"

    class _RunInfo:
        run_id = "run-xyz"

    class _Run:
        info = _RunInfo()

    monkeypatch.setattr("src.models.lifecycle.mlflow.active_run", lambda: _Run())
    monkeypatch.setattr("src.models.lifecycle.mlflow.log_artifact", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "src.models.lifecycle.mlflow.get_artifact_uri",
        lambda path="": f"s3://mlflow-artifacts/1/run-xyz/artifacts/{path}",
    )
    monkeypatch.setattr("src.models.lifecycle.mlflow.set_tags", lambda tags: None)
    monkeypatch.setattr("src.models.lifecycle.mlflow.set_tag", lambda key, value: None)
    monkeypatch.setattr("src.models.lifecycle.mlflow.log_dict", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.mlops.promotion.validate_promoted_artifacts", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "src.models.lifecycle.export_model_to_onnx",
        lambda **kwargs: ONNXExportResult(
            status="success",
            reason="ok",
            raw_path=raw_onnx,
            fp16_path=fp16_onnx,
            validated=True,
            smoke_test_passed=True,
        ),
    )

    entry = finalize_model_lifecycle(
        model_name="sla_5g",
        model_family="xgboost_classifier",
        artifact_format="xgboost_ubj",
        metrics={"val_roc_auc": 0.9},
        local_artifact_path=artifact_path,
        task_type="binary_classification",
        experiment_name="neuroslice-aiops",
        preprocessor_path=preprocessor_path,
        input_schema={"features": ["f1", "f2"]},
        model=object(),
        export_kind="xgboost",
        export_basename="sla_5g",
        example_input=[[0.1, 0.2]],
        registry_path=registry_path,
    )

    promoted_current_fp16 = models_dir / "promoted" / "sla_5g" / "current" / "model_fp16.onnx"
    promoted_current_meta = models_dir / "promoted" / "sla_5g" / "current" / "metadata.json"
    promoted_version_fp16 = models_dir / "promoted" / "sla_5g" / "1" / "model_fp16.onnx"

    assert entry["promoted"] is True
    assert entry["stage"] == "production"
    assert promoted_current_fp16.exists()
    assert promoted_version_fp16.exists()
    assert promoted_current_meta.exists()

    metadata = json.loads(promoted_current_meta.read_text(encoding="utf-8"))
    assert metadata["model_name"] == "sla_5g"
    assert metadata["deployment_name"] == "sla_5g"
    assert metadata["version"] == "1"
    assert metadata["run_id"] == "run-xyz"
    assert metadata["updated_at"]
    assert metadata["framework"] == "xgboost"


def test_promote_onnx_artifacts_writes_versioned_and_current_metadata(tmp_path, monkeypatch):
    raw_onnx = tmp_path / "model.onnx"
    fp16_onnx = tmp_path / "model_fp16.onnx"
    raw_onnx.write_text("raw", encoding="utf-8")
    fp16_onnx.write_text("fp16", encoding="utf-8")
    monkeypatch.setattr("src.mlops.promotion.validate_promoted_artifacts", lambda *args, **kwargs: None)

    result = promote_onnx_artifacts(
        model_name="slice_type_5g",
        version="7",
        run_id="run-7",
        metrics={"val_accuracy": 0.93},
        framework="lightgbm_classifier",
        raw_onnx_path=raw_onnx,
        fp16_onnx_path=fp16_onnx,
        promoted_root=tmp_path / "promoted",
        created_at="2026-04-26T00:00:00+00:00",
        updated_at="2026-04-26T01:00:00+00:00",
        registered_model_name="slice-type-lgbm-5g",
    )

    assert result.raw_path.exists()
    assert result.fp16_path.exists()
    assert result.current_fp16_path.exists()
    assert result.current_metadata_path.exists()

    metadata = json.loads(result.current_metadata_path.read_text(encoding="utf-8"))
    assert metadata == {
        "model_name": "slice-type-lgbm-5g",
        "deployment_name": "slice_type_5g",
        "version": "7",
        "run_id": "run-7",
        "updated_at": "2026-04-26T01:00:00+00:00",
        "metrics": {"val_accuracy": 0.93},
        "created_at": "2026-04-26T00:00:00+00:00",
        "framework": "lightgbm",
    }


def test_materialize_promoted_model_uses_mlflow_deployment_version(tmp_path, monkeypatch):
    models_dir = tmp_path / "models"
    onnx_dir = models_dir / "onnx"
    onnx_dir.mkdir(parents=True)
    (onnx_dir / "sla_5g.onnx").write_text("raw", encoding="utf-8")
    (onnx_dir / "sla_5g_fp16.onnx").write_text("fp16", encoding="utf-8")
    registry_path = models_dir / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "generated_at": None,
                "models": [
                    {
                        "model_name": "sla_5g",
                        "version": 2,
                        "deployment_version": "9",
                        "stage": "production",
                        "promoted": True,
                        "onnx_export_status": "success",
                        "onnx_path": "onnx/sla_5g.onnx",
                        "onnx_fp16_path": "onnx/sla_5g_fp16.onnx",
                        "metrics": {"val_roc_auc": 0.88},
                        "framework": "xgboost",
                        "registered_model_name": "sla-xgboost-5g",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("src.mlops.promotion.validate_promoted_artifacts", lambda *args, **kwargs: None)

    entry = materialize_promoted_model_for_registry(model_name="sla_5g", registry_path=registry_path)

    assert entry["promoted_artifact_status"] == "ready"
    assert (models_dir / "promoted" / "sla_5g" / "9" / "model.onnx").exists()
    metadata = json.loads((models_dir / "promoted" / "sla_5g" / "current" / "metadata.json").read_text())
    assert metadata["model_name"] == "sla-xgboost-5g"
    assert metadata["deployment_name"] == "sla_5g"
    assert metadata["version"] == "9"
    assert metadata["updated_at"]


def test_convert_to_fp16_uses_onnxconverter_common(tmp_path, monkeypatch):
    source = tmp_path / "model.onnx"
    target = tmp_path / "model_fp16.onnx"
    source.write_text("raw", encoding="utf-8")

    class _FakeOnnx:
        @staticmethod
        def load(path):
            assert path == source.as_posix()
            return "model"

        @staticmethod
        def save(model, path):
            assert model == "fp16-model"
            Path(path).write_text("fp16", encoding="utf-8")

    class _FakeFloat16:
        @staticmethod
        def convert_float_to_float16(model):
            assert model == "model"
            return "fp16-model"

    import sys
    import types
    from pathlib import Path

    monkeypatch.setitem(sys.modules, "onnx", _FakeOnnx)
    fake_common = types.SimpleNamespace(float16=_FakeFloat16)
    monkeypatch.setitem(sys.modules, "onnxconverter_common", fake_common)

    assert convert_to_fp16(source, target) == target
    assert target.read_text(encoding="utf-8") == "fp16"


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
