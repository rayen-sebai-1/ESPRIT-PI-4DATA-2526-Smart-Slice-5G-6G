"""Reusable ONNX export and FP16 conversion helpers for NeuroSlice MLOps."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_ONNX_OUTPUT_DIR = ROOT_DIR / "models" / "onnx"
DEFAULT_OPSET = int(os.getenv("ONNX_OPSET_VERSION", "18"))
DEFAULT_FIXED_SEQUENCE_LENGTH = int(
    os.getenv("PYTORCH_ONNX_FIXED_SEQUENCE_LENGTH", "30")
)


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
    pytorch_fixed_sequence_length: int | None = None,
) -> ONNXExportResult:
    """Export a model to ONNX, produce FP16, and optionally execute a smoke test."""
    onnx_dir = Path(output_dir or DEFAULT_ONNX_OUTPUT_DIR)
    raw_path = onnx_dir / f"{output_basename}.onnx"
    fp16_path = onnx_dir / f"{output_basename}_fp16.onnx"

    try:
        onnx_dir.mkdir(parents=True, exist_ok=True)
        example_array = _as_numpy_array(example_input)

        if export_kind == "pytorch":
            export_pytorch_to_onnx(
                model=model,
                output_path=raw_path,
                example_input=example_array,
                input_names=input_names,
                output_names=output_names,
                dynamic_axes=dynamic_axes,
                fixed_sequence_length=pytorch_fixed_sequence_length,
                opset_version=opset_version,
            )
        elif export_kind == "xgboost":
            export_xgboost_to_onnx(
                model=model,
                output_path=raw_path,
                example_input=example_array,
                opset_version=opset_version,
            )
        elif export_kind == "lightgbm":
            export_lightgbm_to_onnx(
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


def export_pytorch_to_onnx(
    *,
    model: Any,
    output_path: Path,
    example_input: Any,
    input_names: Sequence[str] | None = None,
    output_names: Sequence[str] | None = None,
    dynamic_axes: Mapping[str, Mapping[int, str]] | None = None,
    fixed_sequence_length: int | None = None,
    opset_version: int = DEFAULT_OPSET,
) -> None:
    """Export a PyTorch model to ONNX using a stable dummy input.

    When fixed_sequence_length is provided, axis 1 is kept static to avoid dynamic
    dim hint conflicts observed with LSTM traces.
    """
    import torch

    in_name = list(input_names or ["input"])[0]
    out_name = list(output_names or ["output"])[0]
    fixed_len = int(fixed_sequence_length) if fixed_sequence_length else None

    input_array = _prepare_pytorch_input(_as_numpy_array(example_input), fixed_len)
    tensor = torch.as_tensor(input_array, dtype=torch.float32)

    export_kwargs = {
        "export_params": True,
        "do_constant_folding": True,
        "input_names": [in_name],
        "output_names": [out_name],
        "dynamic_axes": _sanitize_dynamic_axes(
            dynamic_axes=dynamic_axes,
            input_name=in_name,
            output_name=out_name,
            fixed_sequence_length=fixed_len,
        ),
        "opset_version": max(18, int(opset_version)),
    }

    model_cpu = model.to("cpu")
    model_cpu.eval()

    try:
        torch.onnx.export(
            model_cpu,
            tensor,
            output_path.as_posix(),
            dynamo=False,
            **export_kwargs,
        )
    except TypeError as exc:
        if "dynamo" not in str(exc):
            raise
        torch.onnx.export(
            model_cpu,
            tensor,
            output_path.as_posix(),
            **export_kwargs,
        )


def export_xgboost_to_onnx(
    *,
    model: Any,
    output_path: Path,
    example_input: Any,
    opset_version: int = DEFAULT_OPSET,
) -> None:
    """Export an XGBoost model to ONNX."""
    import onnxmltools
    from onnxmltools.convert.common._topology import get_maximum_opset_supported
    from onnxmltools.convert.common.data_types import FloatTensorType

    example_array = _as_numpy_array(example_input)
    n_features = _feature_count(example_array)
    target_opset = min(int(opset_version), int(get_maximum_opset_supported()))
    onnx_model = onnxmltools.convert_xgboost(
        model,
        initial_types=[("input", FloatTensorType([None, n_features]))],
        target_opset=target_opset,
    )
    _ensure_default_domain_opset(onnx_model, target_opset)
    onnxmltools.utils.save_model(onnx_model, output_path.as_posix())
    _validate_onnxruntime_roundtrip(output_path, example_array)


def export_lightgbm_to_onnx(
    *,
    model: Any,
    output_path: Path,
    example_input: Any,
    opset_version: int = DEFAULT_OPSET,
) -> None:
    """Export a LightGBM model to ONNX."""
    import onnxmltools
    from onnxmltools.convert.common._topology import get_maximum_opset_supported
    from onnxmltools.convert.common.data_types import FloatTensorType

    example_array = _as_numpy_array(example_input)
    n_features = _feature_count(example_array)
    target_opset = min(int(opset_version), int(get_maximum_opset_supported()))
    onnx_model = onnxmltools.convert_lightgbm(
        model,
        initial_types=[("input", FloatTensorType([None, n_features]))],
        target_opset=target_opset,
    )
    _ensure_default_domain_opset(onnx_model, target_opset)
    onnxmltools.utils.save_model(onnx_model, output_path.as_posix())
    _validate_onnxruntime_roundtrip(output_path, example_array)


def validate_onnx_model(model_path: Path) -> None:
    """Run structural validation on an ONNX model."""
    import onnx

    model_proto = onnx.load(model_path.as_posix())
    onnx.checker.check_model(model_proto)


def convert_onnx_to_fp16(
    source_path: Path,
    target_path: Path,
    *,
    keep_fp32_io: bool = True,
) -> None:
    """Convert a float32 ONNX graph to FP16 while optionally keeping float32 I/O."""
    import onnx
    from onnxconverter_common import float16

    model_proto = onnx.load(source_path.as_posix())
    fp16_model = float16.convert_float_to_float16(
        model_proto, keep_io_types=keep_fp32_io
    )
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


def _prepare_pytorch_input(
    example_array: np.ndarray, fixed_sequence_length: int | None
) -> np.ndarray:
    array = np.asarray(example_array, dtype=np.float32)

    if array.ndim == 1:
        array = array.reshape(1, -1)

    if fixed_sequence_length is None:
        if array.ndim == 2:
            return array
        if array.ndim == 3:
            return array
        return np.asarray(array, dtype=np.float32)

    if array.ndim == 2:
        # Interpret as (sequence, features) and enforce fixed (1, T, F).
        sequence_source = array
    elif array.ndim == 3:
        sequence_source = array[0]
    else:
        return np.asarray(array, dtype=np.float32)

    num_features = int(sequence_source.shape[-1])
    fixed = np.zeros((1, int(fixed_sequence_length), num_features), dtype=np.float32)
    copy_length = min(int(fixed_sequence_length), int(sequence_source.shape[0]))
    fixed[0, :copy_length, :] = sequence_source[:copy_length, :]
    return fixed


def _sanitize_dynamic_axes(
    *,
    dynamic_axes: Mapping[str, Mapping[int, str]] | None,
    input_name: str,
    output_name: str,
    fixed_sequence_length: int | None,
) -> dict[str, dict[int, str]]:
    if dynamic_axes is None:
        return {
            input_name: {0: "batch"},
            output_name: {0: "batch"},
        }

    sanitized: dict[str, dict[int, str]] = {}
    for tensor_name, axes in dynamic_axes.items():
        tensor_axes: dict[int, str] = {}
        for axis, axis_name in axes.items():
            if (
                fixed_sequence_length is not None
                and tensor_name == input_name
                and int(axis) == 1
            ):
                continue
            tensor_axes[int(axis)] = str(axis_name)
        if tensor_axes:
            sanitized[tensor_name] = tensor_axes

    sanitized.setdefault(input_name, {0: "batch"})
    sanitized.setdefault(output_name, {0: "batch"})
    return sanitized


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


def _ensure_default_domain_opset(onnx_model: Any, target_opset: int) -> None:
    """Ensure the default ONNX domain has an opset import for Cast and other core ops."""
    for import_entry in onnx_model.opset_import:
        if import_entry.domain == "":
            import_entry.version = max(int(import_entry.version), int(target_opset))
            return

    new_entry = onnx_model.opset_import.add()
    new_entry.domain = ""
    new_entry.version = int(target_opset)


def _validate_onnxruntime_roundtrip(
    model_path: Path, example_input: np.ndarray
) -> None:
    """Validate exported ONNX graph by loading it in ONNX Runtime and running one inference."""
    import onnxruntime as ort

    session = ort.InferenceSession(
        model_path.as_posix(), providers=["CPUExecutionProvider"]
    )
    input_meta = session.get_inputs()[0]
    input_dtype = np.float16 if "float16" in input_meta.type else np.float32
    feed = {input_meta.name: np.asarray(example_input, dtype=input_dtype)}
    session.run(None, feed)
