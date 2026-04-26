"""Model loading for congestion-detector."""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from typing import Any, Optional

import joblib

from config import CongestionConfig
from shared.model_hot_reload import current_promoted_snapshot, promoted_current_paths
from shared.onnx_runtime import onnxruntime_available

logger = logging.getLogger(__name__)


@dataclass
class CongestionModelBundle:
    model: Optional[Any]
    preprocessor: Optional[Any]
    loaded: bool
    model_version: str
    sequence_length: int
    model_source: str
    model_format: str
    fallback_mode: bool
    onnxruntime_enabled: bool
    metadata_mtime_ns: int = 0
    model_mtime_ns: int = 0


class CongestionModelLoader:
    def __init__(self, cfg: CongestionConfig) -> None:
        self.cfg = cfg

    def load(self) -> CongestionModelBundle:
        model = None
        preprocessor = None
        sequence_length = self.cfg.sequence_length
        model_source = "heuristic"
        model_format = "heuristic"
        discovered_version = ""
        metadata_mtime_ns = 0
        model_mtime_ns = 0
        onnx_enabled = onnxruntime_available()
        promoted_snapshot = current_promoted_snapshot(self.cfg.model_registry_path, self.cfg.registry_model_name)
        promoted_model_path, _ = promoted_current_paths(self.cfg.model_registry_path, self.cfg.registry_model_name)

        # Make mlops source importable so joblib can resolve class symbols.
        if os.path.isdir("/mlops") and "/mlops" not in sys.path:
            sys.path.insert(0, "/mlops")

        if self.cfg.model_format == "onnx_fp16" and onnx_enabled and promoted_snapshot is not None:
            try:
                model = self._load_onnx_session(promoted_snapshot.model_path.as_posix())
                model_source = promoted_snapshot.model_path.as_posix()
                model_format = "onnx_fp16"
                discovered_version = promoted_snapshot.version
                metadata_mtime_ns = promoted_snapshot.metadata_mtime_ns
                model_mtime_ns = promoted_snapshot.model_mtime_ns
                logger.info("Loaded promoted congestion ONNX model from %s", promoted_snapshot.model_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not load promoted current congestion ONNX model: %s", exc)
        elif not onnx_enabled:
            logger.warning("ONNX Runtime is unavailable; congestion service will use heuristic fallback")
        elif promoted_snapshot is None:
            logger.warning(
                "Promoted congestion ONNX model not found at %s",
                promoted_model_path,
            )

        try:
            if os.path.exists(self.cfg.preprocessor_path):
                preprocessor = joblib.load(self.cfg.preprocessor_path)
                if hasattr(preprocessor, "seq_length"):
                    sequence_length = int(preprocessor.seq_length)
                logger.info("Loaded congestion preprocessor from %s", self.cfg.preprocessor_path)
            else:
                logger.warning("Congestion preprocessor not found at %s", self.cfg.preprocessor_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load congestion preprocessor: %s", exc)

        model_version = discovered_version or self.cfg.model_version.strip() or "heuristic"

        loaded = model is not None
        fallback_mode = model_format != "onnx_fp16"
        logger.info(
            "model_loaded=%s model_format=%s model_version=%s fallback_mode=%s "
            "onnxruntime_enabled=%s model_source=%s sequence_length=%d",
            loaded,
            model_format,
            model_version,
            fallback_mode,
            onnx_enabled,
            model_source,
            sequence_length,
        )
        if not loaded:
            logger.warning("Congestion runtime model unavailable, service will run with heuristic fallback")

        return CongestionModelBundle(
            model=model,
            preprocessor=preprocessor,
            loaded=loaded,
            model_version=model_version,
            sequence_length=sequence_length,
            model_source=model_source,
            model_format=model_format,
            fallback_mode=fallback_mode,
            onnxruntime_enabled=onnx_enabled,
            metadata_mtime_ns=metadata_mtime_ns,
            model_mtime_ns=model_mtime_ns,
        )

    @staticmethod
    def _load_onnx_session(model_path: str) -> Any:
        import onnxruntime as ort

        return ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])

