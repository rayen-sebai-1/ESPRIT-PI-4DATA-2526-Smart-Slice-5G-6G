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

logger = logging.getLogger(__name__)


@dataclass
class SliceModelBundle:
    model: Optional[Any]
    label_encoder: Optional[Any]
    loaded: bool
    model_version: str
    model_source: str


class SliceModelLoader:
    def __init__(self, cfg: SliceClassifierConfig) -> None:
        self.cfg = cfg

    def load(self) -> SliceModelBundle:
        model = None
        model_source = "heuristic"
        discovered_version = ""

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

        # 1) explicit path wins
        if self.cfg.model_path and os.path.exists(self.cfg.model_path):
            try:
                model = joblib.load(self.cfg.model_path)
                model_source = self.cfg.model_path
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

        model_version = self.cfg.model_version.strip() or discovered_version or "heuristic"
        loaded = model is not None and label_encoder is not None

        if loaded:
            logger.info("Slice model ready (version=%s source=%s)", model_version, model_source)
        else:
            logger.warning("Slice model unavailable, runtime will use heuristic classification")

        return SliceModelBundle(
            model=model,
            label_encoder=label_encoder,
            loaded=loaded,
            model_version=model_version,
            model_source=model_source,
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
