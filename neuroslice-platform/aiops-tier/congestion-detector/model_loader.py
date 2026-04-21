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

logger = logging.getLogger(__name__)


@dataclass
class CongestionModelBundle:
    model: Optional[Any]
    preprocessor: Optional[Any]
    loaded: bool
    model_version: str
    sequence_length: int
    model_source: str


class CongestionModelLoader:
    def __init__(self, cfg: CongestionConfig) -> None:
        self.cfg = cfg

    def load(self) -> CongestionModelBundle:
        model = None
        preprocessor = None
        sequence_length = self.cfg.sequence_length
        model_source = "heuristic"

        # Make mlops source importable so joblib can resolve class symbols.
        if os.path.isdir("/mlops") and "/mlops" not in sys.path:
            sys.path.insert(0, "/mlops")

        try:
            import torch

            if os.path.exists(self.cfg.model_path):
                model = torch.jit.load(self.cfg.model_path)
                model.eval()
                model_source = self.cfg.model_path
                logger.info("Loaded congestion model from %s", self.cfg.model_path)
            else:
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

        model_version = self.cfg.model_version.strip() or self._derive_version(self.cfg.model_path)

        loaded = model is not None
        if loaded:
            logger.info(
                "Congestion runtime model ready (version=%s, sequence_length=%d)",
                model_version,
                sequence_length,
            )
        else:
            logger.warning("Congestion runtime model unavailable, service will run with heuristic fallback")

        return CongestionModelBundle(
            model=model,
            preprocessor=preprocessor,
            loaded=loaded,
            model_version=model_version,
            sequence_length=sequence_length,
            model_source=model_source,
        )

    @staticmethod
    def _derive_version(path: str) -> str:
        if not path or not os.path.exists(path):
            return "heuristic"
        stat = os.stat(path)
        ts = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"{os.path.basename(path)}@{ts}"
