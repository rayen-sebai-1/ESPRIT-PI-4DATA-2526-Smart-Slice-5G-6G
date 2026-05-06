from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("MLOPS_SCHEDULE_ENABLED", "false")
os.environ.setdefault("MLOPS_PENDING_RECONCILE_ON_STARTUP", "false")


@pytest.fixture
def models_dir(tmp_path: Path) -> Path:
    """Build a minimal model registry layout for tests."""
    models = tmp_path / "models"
    promoted = models / "promoted" / "sla_5g" / "current"
    promoted.mkdir(parents=True)

    (promoted / "model.onnx").write_bytes(b"\x00")
    (promoted / "model_fp16.onnx").write_bytes(b"\x00")
    (promoted / "metadata.json").write_text(
        json.dumps(
            {
                "model_name": "sla-xgboost-5g",
                "deployment_name": "sla_5g",
                "version": "2",
                "run_id": "abc123",
                "framework": "xgboost",
                "updated_at": "2026-04-27T10:55:08+00:00",
                "created_at": "2026-04-27T10:55:08+00:00",
                "metrics": {"val_f1": 0.89, "val_roc_auc": 0.99},
            }
        ),
        encoding="utf-8",
    )

    registry = {
        "generated_at": "2026-04-27T11:00:00+00:00",
        "models": [
            {
                "model_name": "sla_5g",
                "version": 12,
                "stage": "production",
                "promoted": True,
                "framework": "xgboost",
                "model_family": "xgboost_classifier",
                "quality_gate_status": "pass",
                "promotion_status": "promoted",
                "onnx_export_status": "success",
                "created_at": "2026-04-27T10:55:08+00:00",
                "run_id": "abc123",
                "metrics": {"val_f1": 0.89, "val_roc_auc": 0.99},
                "reason": "val_roc_auc=0.99 meets threshold.",
                "deployment_name": "sla_5g",
            },
            {
                "model_name": "congestion_5g",
                "version": 5,
                "stage": "rejected",
                "promoted": False,
                "framework": "pytorch",
                "model_family": "pytorch_lstm",
                "quality_gate_status": "fail",
                "promotion_status": "rejected",
                "onnx_export_status": "failed",
                "created_at": "2026-04-26T10:00:00+00:00",
                "run_id": "def456",
                "metrics": {"val_f1": 0.36, "val_roc_auc": 0.98},
                "reason": "val_precision below threshold.",
            },
        ],
    }
    (models / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
    return models
