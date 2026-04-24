"""Shared ONNX Runtime helpers for AIOps service loaders."""
from __future__ import annotations

from typing import Any

import numpy as np


def onnxruntime_available() -> bool:
    try:
        import onnxruntime  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


def load_session(path: str) -> Any:
    import onnxruntime as ort

    return ort.InferenceSession(path, providers=["CPUExecutionProvider"])


def run_session(session: Any, features: np.ndarray) -> list[Any]:
    input_meta = session.get_inputs()[0]
    input_dtype = np.float16 if "float16" in input_meta.type else np.float32
    array = np.asarray(features, dtype=input_dtype)
    return session.run(None, {input_meta.name: array})


class ONNXClassifierAdapter:
    def __init__(self, session: Any) -> None:
        self.session = session

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        outputs = run_session(self.session, np.asarray(features))
        return extract_probabilities(outputs)

    def predict(self, features: np.ndarray) -> np.ndarray:
        probabilities = self.predict_proba(features)
        return np.argmax(probabilities, axis=1)


def extract_probabilities(outputs: list[Any]) -> np.ndarray:
    for output in reversed(outputs):
        if isinstance(output, np.ndarray) and output.dtype != object:
            if output.ndim == 2:
                return output.astype(np.float32)
            if output.ndim == 1:
                if np.all((0.0 <= output) & (output <= 1.0)):
                    return np.column_stack([1.0 - output, output]).astype(np.float32)
                return output.reshape(-1, 1).astype(np.float32)

        rows = _dict_rows(output)
        if rows is not None:
            return rows

    raise ValueError("Could not extract probability outputs from ONNX Runtime results.")


def _dict_rows(output: Any) -> np.ndarray | None:
    if isinstance(output, list) and output and isinstance(output[0], dict):
        return _convert_probability_maps(output)

    if isinstance(output, np.ndarray) and output.dtype == object and output.size > 0:
        first = output.flat[0]
        if isinstance(first, dict):
            return _convert_probability_maps(list(output.flat))

    return None


def _convert_probability_maps(rows: list[dict[Any, Any]]) -> np.ndarray:
    class_keys = sorted({int(key) for row in rows for key in row})
    matrix = []
    for row in rows:
        matrix.append([float(row.get(key, 0.0)) for key in class_keys])
    return np.asarray(matrix, dtype=np.float32)
