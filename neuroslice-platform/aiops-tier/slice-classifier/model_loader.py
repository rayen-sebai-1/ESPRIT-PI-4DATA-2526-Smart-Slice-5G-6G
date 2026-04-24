"""Model loading for slice-classifier."""
from __future__ import annotations

import glob
import logging
import os
import sqlite3
from dataclasses import dataclass
from typing import Any, Optional, Tuple

import joblib

from config import SliceClassifierConfig
from shared.model_registry_client import ModelRegistryClient
from shared.onnx_runtime import ONNXClassifierAdapter, load_session, onnxruntime_available

logger = logging.getLogger(__name__)


@dataclass
class SliceModelBundle:
    model: Optional[Any]
    label_encoder: Optional[Any]
    loaded: bool
    model_version: str
    model_source: str
    model_format: str
    fallback_mode: bool
    onnxruntime_enabled: bool


class SliceModelLoader:
    def __init__(self, cfg: SliceClassifierConfig) -> None:
        self.cfg = cfg

    def load(self) -> SliceModelBundle:
        model = None
        model_source = "heuristic"
        discovered_version = ""
        model_format = "heuristic"
        onnx_enabled = onnxruntime_available()

        # Label encoder can exist independently and is used by both model and fallback.
        label_encoder = None
        if os.path.exists(self.cfg.label_encoder_path):
            try:
                label_encoder = joblib.load(self.cfg.label_encoder_path)
                logger.info("Loaded slice label encoder from %s", self.cfg.label_encoder_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not load slice label encoder: %s", exc)
        else:
            logger.warning("Slice label encoder not found at %s", self.cfg.label_encoder_path)

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
                        model = ONNXClassifierAdapter(load_session(onnx_path.as_posix()))
                        model_source = onnx_path.as_posix()
                        model_format = "onnx_fp16"
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Could not load promoted slice ONNX model: %s", exc)

            if model is None:
                promoted_local_path = registry_client.resolve_artifact_path(
                    promoted_entry,
                    preferred_format="legacy_local_artifact",
                )
                if promoted_local_path is not None:
                    try:
                        model = joblib.load(promoted_local_path)
                        model_source = promoted_local_path.as_posix()
                        model_format = "legacy_local_artifact"
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Could not load promoted slice local artifact: %s", exc)

        # 1) explicit path wins after promoted registry lookup
        if model is None and self.cfg.model_path and os.path.exists(self.cfg.model_path):
            try:
                model = joblib.load(self.cfg.model_path)
                model_source = self.cfg.model_path
                model_format = "legacy_explicit_path"
                logger.info("Loaded slice model from explicit path %s", self.cfg.model_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not load explicit slice model path: %s", exc)

        # 2) otherwise discover from local mlflow registry metadata
        if model is None:
            model, model_source, discovered_version = self._load_from_local_registry(
                model_name=self.cfg.model_name,
                db_path=self.cfg.mlflow_db_path,
                mlruns_dir=self.cfg.mlruns_dir,
            )
            if model is not None:
                model_format = "legacy_mlflow_registry"

        model_version = self.cfg.model_version.strip() or discovered_version or "heuristic"
        loaded = model is not None and label_encoder is not None
        fallback_mode = model_format != "onnx_fp16"

        logger.info(
            "model_loaded=%s model_format=%s model_version=%s fallback_mode=%s onnxruntime_enabled=%s model_source=%s",
            loaded,
            model_format,
            model_version,
            fallback_mode,
            onnx_enabled,
            model_source,
        )

        if not loaded:
            logger.warning("Slice model unavailable, runtime will use heuristic classification")

        return SliceModelBundle(
            model=model,
            label_encoder=label_encoder,
            loaded=loaded,
            model_version=model_version,
            model_source=model_source,
            model_format=model_format,
            fallback_mode=fallback_mode,
            onnxruntime_enabled=onnx_enabled,
        )

    def _load_from_local_registry(
        self,
        model_name: str,
        db_path: str,
        mlruns_dir: str,
    ) -> Tuple[Optional[Any], str, str]:
        if not os.path.exists(db_path):
            logger.warning("MLflow DB not found at %s", db_path)
            return None, "heuristic", ""

        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            row = cur.execute(
                """
                SELECT version, source
                FROM model_versions
                WHERE name = ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (model_name,),
            ).fetchone()
            conn.close()

            if not row:
                logger.warning("No model versions found for %s", model_name)
                return None, "heuristic", ""

            version, source = int(row[0]), str(row[1])
            model_id = source.split("/")[-1] if source else ""
            if not model_id:
                return None, "heuristic", ""

            pattern = os.path.join(mlruns_dir, "*", "models", model_id, "artifacts", "model.pkl")
            matches = glob.glob(pattern)
            if not matches:
                logger.warning("Could not resolve local artifact for %s (pattern=%s)", model_name, pattern)
                return None, "heuristic", f"{model_name}:v{version}"

            model_path = matches[0]
            model = joblib.load(model_path)
            logger.info("Loaded %s from local registry artifact %s", model_name, model_path)
            return model, model_path, f"{model_name}:v{version}"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed loading slice model from registry metadata: %s", exc)
            return None, "heuristic", ""
