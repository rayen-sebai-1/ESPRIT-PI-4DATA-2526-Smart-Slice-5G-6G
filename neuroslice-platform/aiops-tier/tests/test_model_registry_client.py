"""Tests for the shared AIOps registry client."""

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if ROOT_DIR.as_posix() not in sys.path:
    sys.path.insert(0, ROOT_DIR.as_posix())

from shared.model_registry_client import ModelRegistryClient


def test_should_reload_model_when_promoted_version_changes(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir(parents=True)
    registry_path = models_dir / "registry.json"
    (models_dir / "onnx").mkdir()
    (models_dir / "onnx" / "sla_5g_fp16.onnx").write_text("stub", encoding="utf-8")

    registry = {
        "generated_at": "2026-04-24T00:00:00+00:00",
        "models": [
            {
                "model_name": "sla_5g",
                "version": 2,
                "promotion_status": "promoted",
                "onnx_fp16_path": "onnx/sla_5g_fp16.onnx",
                "local_artifact_path": "sla_5g_model.ubj",
            }
        ],
    }
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    client = ModelRegistryClient(registry_path=registry_path)

    assert client.should_reload_model("1", "sla_5g")
    assert not client.should_reload_model("2", "sla_5g")


def test_resolve_artifact_path_prefers_registry_relative_onnx_file(tmp_path):
    models_dir = tmp_path / "models"
    onnx_dir = models_dir / "onnx"
    onnx_dir.mkdir(parents=True)
    artifact_path = onnx_dir / "slice_type_5g_fp16.onnx"
    artifact_path.write_text("stub", encoding="utf-8")

    registry_path = models_dir / "registry.json"
    registry_path.write_text(json.dumps({"generated_at": None, "models": []}), encoding="utf-8")

    client = ModelRegistryClient(registry_path=registry_path)
    resolved = client.resolve_artifact_path(
        {"onnx_fp16_path": "onnx/slice_type_5g_fp16.onnx", "local_artifact_path": "slice_type_5g_model.pkl"}
    )

    assert resolved == artifact_path.resolve()
