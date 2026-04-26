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


def test_promoted_model_supports_new_production_schema(tmp_path):
    models_dir = tmp_path / "models"
    onnx_dir = models_dir / "onnx"
    onnx_dir.mkdir(parents=True)
    artifact_path = onnx_dir / "congestion_5g_fp16.onnx"
    artifact_path.write_text("stub", encoding="utf-8")

    registry_path = models_dir / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-25T00:00:00+00:00",
                "models": [
                    {
                        "model_name": "congestion_5g",
                        "version": 4,
                        "stage": "production",
                        "promoted": True,
                        "format": "onnx_fp16",
                        "onnx_fp16_uri": "s3://mlflow-artifacts/1/run/artifacts/onnx/congestion_5g_fp16.onnx",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    client = ModelRegistryClient(registry_path=registry_path)
    entry = client.get_promoted_model("congestion_5g")
    resolved = client.resolve_artifact_path(entry)

    assert entry["version"] == 4
    assert resolved == artifact_path.resolve()


def test_resolve_artifact_path_prefers_fp16_then_onnx_then_local(tmp_path):
    models_dir = tmp_path / "models"
    onnx_dir = models_dir / "onnx"
    onnx_dir.mkdir(parents=True)
    raw_onnx = onnx_dir / "sla_5g.onnx"
    raw_onnx.write_text("stub", encoding="utf-8")
    local_artifact = models_dir / "sla_5g_model.ubj"
    local_artifact.write_text("stub", encoding="utf-8")

    registry_path = models_dir / "registry.json"
    registry_path.write_text(json.dumps({"generated_at": None, "models": []}), encoding="utf-8")

    client = ModelRegistryClient(registry_path=registry_path)
    resolved = client.resolve_artifact_path(
        {
            "onnx_uri": "s3://mlflow-artifacts/1/run/artifacts/onnx/sla_5g.onnx",
            "artifact_uri": "s3://mlflow-artifacts/1/run/artifacts/models/sla_5g_model.ubj",
            "local_artifact_path": "sla_5g_model.ubj",
        }
    )

    assert resolved == raw_onnx.resolve()


def test_resolve_artifact_path_supports_promoted_current_fp16_path(tmp_path):
    models_dir = tmp_path / "models"
    promoted_current = models_dir / "promoted" / "sla_5g" / "current"
    promoted_current.mkdir(parents=True)
    fp16_path = promoted_current / "model_fp16.onnx"
    fp16_path.write_text("stub", encoding="utf-8")

    registry_path = models_dir / "registry.json"
    registry_path.write_text(json.dumps({"generated_at": None, "models": []}), encoding="utf-8")

    client = ModelRegistryClient(registry_path=registry_path)
    resolved = client.resolve_artifact_path(
        {
            "model_name": "sla_5g",
            "promoted_current_fp16_path": "promoted/sla_5g/current/model_fp16.onnx",
            "onnx_fp16_uri": "s3://mlflow-artifacts/1/run/artifacts/onnx/sla_5g_fp16.onnx",
        }
    )

    assert resolved == fp16_path.resolve()
