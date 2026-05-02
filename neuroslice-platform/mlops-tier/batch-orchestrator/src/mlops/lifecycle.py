"""Centralized post-training lifecycle orchestration for ONNX deployment."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from src.mlops.promotion import PromotionResult, promote_model

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT_DIR / "models"
ONNX_DIR = MODELS_DIR / "onnx"


def run_model_lifecycle(
    model_name: str, run_id: str, onnx_path: str
) -> PromotionResult:
    """Run ONNX deployment lifecycle: export resolution, FP16 conversion, and promotion."""
    if not model_name:
        raise ValueError("model_name must not be empty.")
    if not run_id:
        raise ValueError("run_id must not be empty.")
    if not onnx_path:
        raise ValueError("onnx_path must not be empty.")

    try:
        _emit_info(f"Running lifecycle for {model_name}")
        resolved_onnx_path = _export_onnx_if_needed(
            model_name=model_name, onnx_path=onnx_path
        )
        _emit_info(f"Exported ONNX model: {resolved_onnx_path.as_posix()}")

        fp16_path = _convert_to_fp16(resolved_onnx_path)
        _emit_info(f"Converted {model_name} to FP16")

        result = promote_model(
            model_name=model_name,
            run_id=run_id,
            onnx_path=resolved_onnx_path,
            fp16_path=fp16_path,
        )
        _emit_info(f"Promoted {model_name} to current version {result.version}")
        return result
    except Exception:
        logger.exception(
            "Model lifecycle failed for %s (run_id=%s)", model_name, run_id
        )
        raise


def _export_onnx_if_needed(*, model_name: str, onnx_path: str) -> Path:
    """Resolve the exported ONNX artifact and materialize it at the requested path if needed."""
    requested_path = _resolve_requested_path(onnx_path)
    if requested_path.exists():
        return requested_path

    fallback_candidates = [
        ONNX_DIR / f"{model_name}.onnx",
        ONNX_DIR / Path(onnx_path).name,
    ]
    for candidate in fallback_candidates:
        if candidate.exists():
            requested_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate, requested_path)
            return requested_path

    raise FileNotFoundError(
        f"Could not find exported ONNX model for '{model_name}'. "
        f"Checked '{requested_path.as_posix()}' and '{ONNX_DIR.as_posix()}'."
    )


def _convert_to_fp16(onnx_path: Path) -> Path:
    """Convert one ONNX file to FP16 and return the converted path."""
    import onnx
    from onnxconverter_common import float16

    fp16_path = onnx_path.with_name(f"{onnx_path.stem}_fp16{onnx_path.suffix}")
    fp16_path.parent.mkdir(parents=True, exist_ok=True)

    model_proto = onnx.load(onnx_path.as_posix())
    fp16_model = float16.convert_float_to_float16(model_proto, keep_io_types=True)
    onnx.save_model(fp16_model, fp16_path.as_posix())
    return fp16_path


def _resolve_requested_path(path_value: str) -> Path:
    """Resolve input path relative to repository root when needed."""
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate.resolve()
    return (ROOT_DIR / candidate).resolve()


def _emit_info(message: str) -> None:
    formatted = f"[INFO] {message}"
    print(formatted)


__all__ = ["run_model_lifecycle"]
