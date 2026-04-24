"""Model loading for congestion-detector."""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import joblib

from config import CongestionConfig
from shared.model_registry_client import ModelRegistryClient
from shared.onnx_runtime import load_session, onnxruntime_available

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
        onnx_enabled = onnxruntime_available()

        # Make mlops source importable so joblib can resolve class symbols.
        if os.path.isdir("/mlops") and "/mlops" not in sys.path:
            sys.path.insert(0, "/mlops")

        registry_client = ModelRegistryClient(
            registry_path=self.cfg.model_registry_path,
            tracking_uri=self.cfg.mlflow_tracking_uri or None,
        )
        promoted_entry = registry_client.get_promoted_model(self.cfg.registry_model_name)
        if promoted_entry:
            discovered_version = str(promoted_entry.get("version", ""))
            if (
                self.cfg.model_format == "onnx_fp16"
                and promoted_entry.get("onnx_fp16_path")
                and onnx_enabled
            ):
                onnx_path = registry_client.resolve_artifact_path(
                    promoted_entry,
                    preferred_format="onnx_fp16",
                )
                if onnx_path is not None:
                    try:
                        model = load_session(onnx_path.as_posix())
                        model_source = onnx_path.as_posix()
                        model_format = "onnx_fp16"
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Could not load promoted congestion ONNX model: %s", exc)

        try:
            import torch

            if model is None and self.cfg.model_path and os.path.exists(self.cfg.model_path):
                model = torch.jit.load(self.cfg.model_path)
                model.eval()
                model_source = self.cfg.model_path
                model_format = "legacy_explicit_path"
                logger.info("Loaded congestion model from %s", self.cfg.model_path)
            elif model is None:
                logger.warning("Congestion model file not found at %s", self.cfg.model_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load congestion model: %s", exc)

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

        model_version = self.cfg.model_version.strip() or discovered_version or self._derive_version(model_source)

        loaded = model is not None
        fallback_mode = model_format != "onnx_fp16"
        logger.info(
            "model_loaded=%s model_format=%s model_version=%s fallback_mode=%s onnxruntime_enabled=%s model_source=%s sequence_length=%d",
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
        )

    @staticmethod
    def _derive_version(path: str) -> str:
        if not path or not os.path.exists(path):
            return "heuristic"
        stat = os.stat(path)
        ts = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"{os.path.basename(path)}@{ts}"
