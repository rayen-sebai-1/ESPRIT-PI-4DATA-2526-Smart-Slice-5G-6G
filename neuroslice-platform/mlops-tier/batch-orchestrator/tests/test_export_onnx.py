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
