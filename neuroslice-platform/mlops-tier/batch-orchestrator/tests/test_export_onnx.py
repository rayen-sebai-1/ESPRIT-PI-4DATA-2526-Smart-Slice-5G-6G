"""Smoke tests for the reusable ONNX exporter."""

import numpy as np
import pytest


def test_export_model_to_onnx_creates_fp16_artifact(tmp_path):
    pytest.importorskip("onnx")
    pytest.importorskip("onnxconverter_common")
    import torch
    from src.models.export_onnx import export_model_to_onnx

    class TinyNet(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.linear = torch.nn.Linear(4, 1)

        def forward(self, x):  # noqa: ANN001
            return self.linear(x)

    model = TinyNet().eval()
    example_input = np.ones((1, 4), dtype=np.float32)

    result = export_model_to_onnx(
        model=model,
        export_kind="pytorch",
        output_basename="tiny_net",
        example_input=example_input,
        output_dir=tmp_path,
        run_smoke_test=False,
    )

    assert result.status == "success", result.reason
    assert (tmp_path / "tiny_net.onnx").exists()
    assert (tmp_path / "tiny_net_fp16.onnx").exists()


def test_export_xgboost_to_onnx_smoke(tmp_path):
    pytest.importorskip("onnx")
    pytest.importorskip("onnxmltools")
    pytest.importorskip("xgboost")

    import xgboost as xgb
    from src.mlops.onnx_export import export_xgboost_to_onnx

    X = np.array(
        [
            [0.1, 0.2, 0.3],
            [0.2, 0.1, 0.4],
            [0.8, 0.7, 0.6],
            [0.9, 0.8, 0.5],
        ],
        dtype=np.float32,
    )
    y = np.array([0, 0, 1, 1], dtype=np.int32)
    model = xgb.XGBClassifier(
        n_estimators=8,
        max_depth=2,
        learning_rate=0.1,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X, y)

    output_path = tmp_path / "xgb_test.onnx"
    export_xgboost_to_onnx(model=model, output_path=output_path, example_input=X[:1])

    assert output_path.exists()


def test_export_lightgbm_to_onnx_smoke(tmp_path):
    pytest.importorskip("onnx")
    pytest.importorskip("onnxmltools")
    pytest.importorskip("lightgbm")

    import lightgbm as lgb
    from src.mlops.onnx_export import export_lightgbm_to_onnx

    X = np.array(
        [
            [0.1, 0.2, 0.3],
            [0.2, 0.1, 0.4],
            [0.8, 0.7, 0.6],
            [0.9, 0.8, 0.5],
        ],
        dtype=np.float32,
    )
    y = np.array([0, 0, 1, 1], dtype=np.int32)
    model = lgb.LGBMClassifier(
        n_estimators=8,
        max_depth=3,
        learning_rate=0.1,
        random_state=42,
        verbose=-1,
    )
    model.fit(X, y)

    output_path = tmp_path / "lgb_test.onnx"
    export_lightgbm_to_onnx(model=model, output_path=output_path, example_input=X[:1])

    assert output_path.exists()
