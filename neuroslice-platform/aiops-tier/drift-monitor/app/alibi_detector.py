"""Alibi Detect MMD drift detection wrapper.

Loads drift_reference.npz + drift_feature_schema.json from the promoted model
directory, builds an MMDDrift detector, and exposes a run() method.

If the reference artifacts are missing or alibi-detect is unavailable, the
detector degrades gracefully and reports a clear status instead of crashing.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

_ALIBI_AVAILABLE: Optional[bool] = None


def _check_alibi() -> bool:
    global _ALIBI_AVAILABLE
    if _ALIBI_AVAILABLE is None:
        try:
            from alibi_detect.cd import MMDDrift  # noqa: F401

            _ALIBI_AVAILABLE = True
            logger.info("alibi-detect available")
        except ImportError:
            _ALIBI_AVAILABLE = False
            logger.warning("alibi-detect not importable — drift detection degraded")
    return _ALIBI_AVAILABLE


class ModelDriftDetector:
    """Per-model MMD drift detector backed by Alibi Detect."""

    def __init__(
        self,
        model_name: str,
        models_base_path: str,
        p_val: float = 0.01,
        window_size: int = 500,
    ) -> None:
        self.model_name = model_name
        self.models_base_path = models_base_path
        self.p_val = p_val
        self.window_size = window_size

        self.x_ref: Optional[np.ndarray] = None
        self.feature_names: List[str] = []
        self.feature_count: int = 0
        self.reference_sample_count: int = 0
        self.deployment_version: str = "unknown"
        # status values:
        # initializing | reference_missing | alibi_unavailable | ready
        self.status: str = "initializing"
        self._detector: Any = None

        self._load_reference()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_reference(self) -> None:
        base = Path(self.models_base_path) / self.model_name / "current"
        ref_path = base / "drift_reference.npz"
        schema_path = base / "drift_feature_schema.json"
        metadata_path = base / "metadata.json"

        if not ref_path.exists():
            logger.warning("[%s] drift_reference.npz missing: %s", self.model_name, ref_path)
            self.status = "reference_missing"
            return

        try:
            data = np.load(ref_path)
            self.x_ref = data["x_ref"].astype(np.float32)
            self.reference_sample_count = len(self.x_ref)
            logger.info(
                "[%s] Loaded drift reference: shape=%s", self.model_name, self.x_ref.shape
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("[%s] Failed to load drift_reference.npz: %s", self.model_name, exc)
            self.status = "reference_missing"
            return

        if schema_path.exists():
            try:
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                self.feature_names = schema.get("feature_names", [])
                self.feature_count = int(
                    schema.get("feature_count", self.x_ref.shape[1] if self.x_ref.ndim > 1 else 0)
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("[%s] Could not read drift_feature_schema.json: %s", self.model_name, exc)
                self.feature_count = self.x_ref.shape[1] if self.x_ref.ndim > 1 else 0

        if metadata_path.exists():
            try:
                meta = json.loads(metadata_path.read_text(encoding="utf-8"))
                self.deployment_version = str(meta.get("version", "unknown"))
            except Exception:  # noqa: BLE001
                pass

        if not _check_alibi():
            self.status = "alibi_unavailable"
            return

        self._init_detector()

    def _init_detector(self) -> None:
        if self.x_ref is None:
            return
        try:
            from alibi_detect.cd import MMDDrift

            # Prefer PyTorch backend to avoid heavy TensorFlow dependency.
            try:
                self._detector = MMDDrift(
                    x_ref=self.x_ref,
                    p_val=self.p_val,
                    backend="pytorch",
                )
                logger.info("[%s] MMDDrift initialized (pytorch backend)", self.model_name)
            except Exception:  # noqa: BLE001
                self._detector = MMDDrift(x_ref=self.x_ref, p_val=self.p_val)
                logger.info("[%s] MMDDrift initialized (default backend)", self.model_name)

            self.status = "ready"
        except Exception as exc:  # noqa: BLE001
            logger.error("[%s] MMDDrift initialization failed: %s", self.model_name, exc)
            self.status = "alibi_unavailable"

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def run(self, x_live: np.ndarray) -> Dict[str, Any]:
        """Run MMD drift test on the live window.

        Returns a dict with keys:
          status, is_drift, p_val, drift_score, window_size
        """
        if self.status == "reference_missing":
            return {
                "status": "reference_missing",
                "is_drift": False,
                "p_val": None,
                "drift_score": None,
            }

        if self.status in ("alibi_unavailable", "initializing") or self._detector is None:
            return {
                "status": "alibi_unavailable",
                "is_drift": False,
                "p_val": None,
                "drift_score": None,
            }

        if len(x_live) < self.window_size:
            return {
                "status": "insufficient_data",
                "is_drift": False,
                "p_val": None,
                "drift_score": None,
                "window_size": len(x_live),
            }

        if self.feature_count > 0 and x_live.ndim > 1 and x_live.shape[1] != self.feature_count:
            logger.warning(
                "[%s] Feature count mismatch: expected=%d got=%d",
                self.model_name,
                self.feature_count,
                x_live.shape[1],
            )
            return {
                "status": "feature_count_mismatch",
                "is_drift": False,
                "p_val": None,
                "drift_score": None,
            }

        try:
            x_sample = x_live[-self.window_size :].astype(np.float32)
            result = self._detector.predict(x_sample)

            data = result.get("data", {})
            is_drift = bool(data.get("is_drift", False))
            p_val = float(data.get("p_val", 1.0))

            distance = data.get("distance")
            if distance is not None:
                drift_score = (
                    float(np.mean(distance))
                    if hasattr(distance, "__len__")
                    else float(distance)
                )
            else:
                drift_score = None

            return {
                "status": "drift_detected" if is_drift else "no_drift",
                "is_drift": is_drift,
                "p_val": p_val,
                "drift_score": drift_score,
                "window_size": len(x_sample),
            }
        except Exception as exc:  # noqa: BLE001
            logger.error("[%s] MMD prediction failed: %s", self.model_name, exc)
            return {
                "status": "error",
                "is_drift": False,
                "p_val": None,
                "drift_score": None,
                "error": str(exc),
            }

    def reload_reference(self) -> None:
        """Reload reference artifacts from disk (e.g. after a new promotion)."""
        self._detector = None
        self.x_ref = None
        self.status = "initializing"
        self._load_reference()
