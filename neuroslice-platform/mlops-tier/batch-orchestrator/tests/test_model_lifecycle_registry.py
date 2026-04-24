"""Tests for registry metadata and promotion rules."""

from src.models.lifecycle import evaluate_promotion, load_registry, write_registry_entry


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
