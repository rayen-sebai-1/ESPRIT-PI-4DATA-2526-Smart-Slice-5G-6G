"""Tests for the offline markdown report generator."""

import json

from src.models import lifecycle
from src.reports.generate_model_report import generate_model_report


def test_generate_model_report_includes_registry_content(tmp_path, monkeypatch):
    registry_path = tmp_path / "registry.json"
    output_path = tmp_path / "model_training_summary.md"
    processed_file = tmp_path / "sla_5g_processed.npz"
    processed_file.write_text("stub", encoding="utf-8")

    monkeypatch.setattr(
        lifecycle,
        "DATASET_STATUS_PATHS",
        {"sla_5g": processed_file},
    )

    registry = {
        "generated_at": "2026-04-24T00:00:00+00:00",
        "models": [
            {
                "model_name": "sla_5g",
                "model_family": "xgboost_classifier",
                "version": 3,
                "created_at": "2026-04-24T00:00:00+00:00",
                "run_id": "run-abc",
                "metrics": {"val_roc_auc": 0.82, "val_precision": 0.77},
                "quality_gate_status": "pass",
                "artifact_format": "onnx_fp16",
                "local_artifact_path": "sla_5g_model.ubj",
                "mlflow_artifact_uri": "s3://mlflow-artifacts/sla_5g",
                "onnx_fp16_path": "onnx/sla_5g_fp16.onnx",
                "onnx_export_status": "success",
                "promotion_status": "promoted",
                "reason": "val_roc_auc=0.8200 meets the >= 0.75 rule.",
                "warnings": [],
                "onnx_export_reason": "ok",
            }
        ],
    }
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    report_file = generate_model_report(
        registry_path=registry_path, output_path=output_path
    )
    content = report_file.read_text(encoding="utf-8")

    assert "Model Training Summary" in content
    assert "sla_5g (v3)" in content
    assert "`run-abc`" in content
    assert "onnx/sla_5g_fp16.onnx" in content
