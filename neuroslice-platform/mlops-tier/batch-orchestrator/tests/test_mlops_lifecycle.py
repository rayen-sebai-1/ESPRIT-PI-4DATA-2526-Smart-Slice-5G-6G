"""Tests for centralized MLOps lifecycle orchestration."""

from __future__ import annotations

import json

import pytest


def _write_identity_onnx(path):
    import onnx
    from onnx import TensorProto, helper

    input_tensor = helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 2])
    output_tensor = helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 2])
    node = helper.make_node("Identity", ["input"], ["output"])
    graph = helper.make_graph([node], "identity_graph", [input_tensor], [output_tensor])
    model = helper.make_model(graph, producer_name="pytest")
    model.opset_import[0].version = 13
    onnx.save_model(model, path.as_posix())


def test_run_model_lifecycle_creates_fp16_and_promoted_metadata(tmp_path, monkeypatch):
    pytest.importorskip("onnx")
    pytest.importorskip("onnxconverter_common")
    pytest.importorskip("onnxruntime")

    import src.mlops.lifecycle as lifecycle
    from src.mlops.promotion import promote_model as base_promote_model

    models_dir = tmp_path / "models"
    onnx_dir = models_dir / "onnx"
    onnx_dir.mkdir(parents=True)

    raw_onnx_path = onnx_dir / "congestion_5g.onnx"
    _write_identity_onnx(raw_onnx_path)

    promoted_dir = models_dir / "promoted"

    monkeypatch.setattr(lifecycle, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(lifecycle, "MODELS_DIR", models_dir)
    monkeypatch.setattr(lifecycle, "ONNX_DIR", onnx_dir)
    monkeypatch.setattr(
        lifecycle,
        "promote_model",
        lambda **kwargs: base_promote_model(promoted_root=promoted_dir, **kwargs),
    )

    result = lifecycle.run_model_lifecycle(
        model_name="congestion_5g",
        run_id="run-123",
        onnx_path="models/congestion_5g.onnx",
    )

    assert (models_dir / "congestion_5g_fp16.onnx").exists()
    assert (promoted_dir / "congestion_5g" / result.version / "model_fp16.onnx").exists()
    assert (promoted_dir / "congestion_5g" / "current" / "model_fp16.onnx").exists()

    metadata_path = promoted_dir / "congestion_5g" / "current" / "metadata.json"
    assert metadata_path.exists()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["version"] == result.version
