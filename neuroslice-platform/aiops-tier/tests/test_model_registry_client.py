"""Tests for the shared AIOps registry client."""

import json
import importlib.util
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if ROOT_DIR.as_posix() not in sys.path:
    sys.path.insert(0, ROOT_DIR.as_posix())

from shared.model_registry_client import ModelRegistryClient
from shared.model_hot_reload import current_promoted_snapshot, should_reload_promoted_model


def _load_congestion_model_loader_module():
    service_dir = ROOT_DIR / "congestion-detector"
    if service_dir.as_posix() not in sys.path:
        sys.path.insert(0, service_dir.as_posix())

    spec = importlib.util.spec_from_file_location("congestion_model_loader_test", service_dir / "model_loader.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def test_promoted_current_snapshot_detects_metadata_version_change(tmp_path):
    models_dir = tmp_path / "models"
    current_dir = models_dir / "promoted" / "sla_5g" / "current"
    current_dir.mkdir(parents=True)
    model_path = current_dir / "model_fp16.onnx"
    metadata_path = current_dir / "metadata.json"
    registry_path = models_dir / "registry.json"

    model_path.write_text("stub", encoding="utf-8")
    metadata_path.write_text(json.dumps({"model_name": "sla_5g", "version": 1}), encoding="utf-8")
    registry_path.write_text(json.dumps({"generated_at": None, "models": []}), encoding="utf-8")

    snapshot = current_promoted_snapshot(registry_path, "sla_5g")

    assert snapshot is not None
    assert not should_reload_promoted_model(
        registry_path=registry_path,
        model_name="sla_5g",
        current_version="1",
        current_model_source=snapshot.model_path.as_posix(),
        current_metadata_mtime_ns=snapshot.metadata_mtime_ns,
        current_model_mtime_ns=snapshot.model_mtime_ns,
    )

    metadata_path.write_text(json.dumps({"model_name": "sla_5g", "version": 2}), encoding="utf-8")

    assert should_reload_promoted_model(
        registry_path=registry_path,
        model_name="sla_5g",
        current_version="1",
        current_model_source=snapshot.model_path.as_posix(),
        current_metadata_mtime_ns=snapshot.metadata_mtime_ns,
        current_model_mtime_ns=snapshot.model_mtime_ns,
    )


def test_congestion_loader_uses_promoted_current_onnx(monkeypatch, tmp_path):
    module = _load_congestion_model_loader_module()
    models_dir = tmp_path / "models"
    current_dir = models_dir / "promoted" / "congestion_5g" / "current"
    current_dir.mkdir(parents=True)
    model_path = current_dir / "model_fp16.onnx"
    metadata_path = current_dir / "metadata.json"
    registry_path = models_dir / "registry.json"

    model_path.write_text("onnx", encoding="utf-8")
    metadata_path.write_text(json.dumps({"model_name": "congestion_5g", "version": "12"}), encoding="utf-8")
    registry_path.write_text(json.dumps({"generated_at": None, "models": []}), encoding="utf-8")

    cfg = module.CongestionConfig()
    cfg.model_registry_path = registry_path.as_posix()
    cfg.registry_model_name = "congestion_5g"
    cfg.model_path = "/mlops/models/congestion_5g_lstm_traced.pt"
    cfg.preprocessor_path = (tmp_path / "missing_preprocessor.pkl").as_posix()

    monkeypatch.setattr(module, "onnxruntime_available", lambda: True)
    monkeypatch.setattr(
        module.CongestionModelLoader,
        "_load_onnx_session",
        staticmethod(lambda path: {"session_path": path}),
    )

    bundle = module.CongestionModelLoader(cfg).load()

    assert bundle.loaded is True
    assert bundle.model == {"session_path": model_path.as_posix()}
    assert bundle.model_format == "onnx_fp16"
    assert bundle.model_version == "12"
    assert bundle.model_source == model_path.as_posix()
    assert bundle.fallback_mode is False
