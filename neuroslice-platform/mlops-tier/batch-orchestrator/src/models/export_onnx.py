"""Reusable ONNX export helpers for the offline model lifecycle."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[2]
ONNX_OUTPUT_DIR = ROOT_DIR / "models" / "onnx"
DEFAULT_OPSET = int(os.getenv("ONNX_OPSET_VERSION", "17"))


@dataclass
class ONNXExportResult:
    status: str
    reason: str
    raw_path: Path | None = None
    fp16_path: Path | None = None
    validated: bool = False
    smoke_test_passed: bool | None = None


def export_model_to_onnx(
    *,
    model: Any,
    export_kind: str,
    output_basename: str,
    example_input: Any,
    output_dir: Path | None = None,
    input_names: Sequence[str] | None = None,
    output_names: Sequence[str] | None = None,
    dynamic_axes: Mapping[str, Mapping[int, str]] | None = None,
    run_smoke_test: bool = False,
    opset_version: int = DEFAULT_OPSET,
) -> ONNXExportResult:
    """Export a model to ONNX and generate an FP16 variant."""
    onnx_dir = Path(output_dir or ONNX_OUTPUT_DIR)
    raw_path = onnx_dir / f"{output_basename}.onnx"
    fp16_path = onnx_dir / f"{output_basename}_fp16.onnx"

    try:
        onnx_dir.mkdir(parents=True, exist_ok=True)
        example_array = _as_numpy_array(example_input)

        if export_kind == "pytorch":
            _export_pytorch_model(
                model=model,
                output_path=raw_path,
                example_input=example_array,
                input_names=input_names,
                output_names=output_names,
                dynamic_axes=dynamic_axes,
                opset_version=opset_version,
            )
        elif export_kind == "xgboost":
            _export_xgboost_model(
                model=model,
                output_path=raw_path,
                example_input=example_array,
                opset_version=opset_version,
            )
        elif export_kind == "lightgbm":
            _export_lightgbm_model(
                model=model,
                output_path=raw_path,
                example_input=example_array,
                opset_version=opset_version,
            )
        else:
            raise ValueError(f"Unsupported export kind '{export_kind}'.")

        validate_onnx_model(raw_path)
        convert_onnx_to_fp16(raw_path, fp16_path)
        validate_onnx_model(fp16_path)

        smoke_test_passed = None
        if run_smoke_test:
            smoke_test_passed = run_onnx_smoke_test(fp16_path, example_array)

        return ONNXExportResult(
            status="success",
            reason="ONNX export completed successfully.",
            raw_path=raw_path,
            fp16_path=fp16_path,
            validated=True,
            smoke_test_passed=smoke_test_passed,
        )
    except Exception as exc:  # noqa: BLE001
        return ONNXExportResult(
            status="failed",
            reason=str(exc),
            raw_path=raw_path if raw_path.exists() else None,
            fp16_path=fp16_path if fp16_path.exists() else None,
            validated=False,
            smoke_test_passed=False if run_smoke_test else None,
        )


def validate_onnx_model(model_path: Path) -> None:
    """Run structural validation on an ONNX model."""
    import onnx

    model_proto = onnx.load(model_path.as_posix())
    onnx.checker.check_model(model_proto)


def convert_onnx_to_fp16(source_path: Path, target_path: Path) -> None:
    """Convert a float32 ONNX graph to FP16 while keeping float32 I/O."""
    import onnx
    from onnxconverter_common import float16

    model_proto = onnx.load(source_path.as_posix())
    fp16_model = float16.convert_float_to_float16(model_proto, keep_io_types=True)
    onnx.save_model(fp16_model, target_path.as_posix())


def run_onnx_smoke_test(model_path: Path, example_input: Any) -> bool:
    """Execute a single ONNX Runtime forward pass."""
    import onnxruntime as ort

    example_array = _as_numpy_array(example_input)
    session = ort.InferenceSession(
        model_path.as_posix(),
        providers=["CPUExecutionProvider"],
    )
    input_meta = session.get_inputs()[0]
    input_dtype = np.float16 if "float16" in input_meta.type else np.float32
    feed = {input_meta.name: example_array.astype(input_dtype, copy=False)}
    session.run(None, feed)
    return True


def _export_pytorch_model(
    *,
    model: Any,
    output_path: Path,
    example_input: np.ndarray,
    input_names: Sequence[str] | None,
    output_names: Sequence[str] | None,
    dynamic_axes: Mapping[str, Mapping[int, str]] | None,
    opset_version: int,
) -> None:
    import torch

    tensor = torch.as_tensor(example_input, dtype=torch.float32)
    if tensor.ndim == 1:
        tensor = tensor.unsqueeze(0)

    model_cpu = model.to("cpu")
    model_cpu.eval()
    torch.onnx.export(
        model_cpu,
        tensor,
        output_path.as_posix(),
        export_params=True,
        do_constant_folding=True,
        input_names=list(input_names or ["input"]),
        output_names=list(output_names or ["output"]),
        dynamic_axes=dynamic_axes or {"input": {0: "batch"}, "output": {0: "batch"}},
        opset_version=opset_version,
    )


def _export_xgboost_model(
    *,
    model: Any,
    output_path: Path,
    example_input: np.ndarray,
    opset_version: int,
) -> None:
    import onnx
    import onnxmltools
    from skl2onnx.common.data_types import FloatTensorType

    n_features = _feature_count(example_input)
    onnx_model = onnxmltools.convert_xgboost(
        model,
        initial_types=[("input", FloatTensorType([None, n_features]))],
        target_opset=opset_version,
    )
    onnx.save_model(onnx_model, output_path.as_posix())


def _export_lightgbm_model(
    *,
    model: Any,
    output_path: Path,
    example_input: np.ndarray,
    opset_version: int,
) -> None:
    import onnx
    import onnxmltools
    from skl2onnx.common.data_types import FloatTensorType

    n_features = _feature_count(example_input)
    onnx_model = onnxmltools.convert_lightgbm(
        model,
        initial_types=[("input", FloatTensorType([None, n_features]))],
        target_opset=opset_version,
    )
    onnx.save_model(onnx_model, output_path.as_posix())


def _feature_count(example_input: np.ndarray) -> int:
    if example_input.ndim == 1:
        return int(example_input.shape[0])
    return int(example_input.shape[-1])


def _as_numpy_array(example_input: Any) -> np.ndarray:
    try:
        import torch

        if isinstance(example_input, torch.Tensor):
            array = example_input.detach().cpu().numpy()
        else:
            array = np.asarray(example_input, dtype=np.float32)
    except Exception:  # noqa: BLE001
        array = np.asarray(example_input, dtype=np.float32)

    if array.dtype != np.float32:
        array = array.astype(np.float32)
    return array
