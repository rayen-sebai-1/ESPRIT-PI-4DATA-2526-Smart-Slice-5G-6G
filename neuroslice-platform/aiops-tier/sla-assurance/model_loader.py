"""Model loading for sla-assurance."""
from __future__ import annotations

import glob
import logging
import os
import sqlite3
from dataclasses import dataclass
from typing import Any, Optional, Tuple

import joblib
import xgboost as xgb

from config import SlaAssuranceConfig

logger = logging.getLogger(__name__)


@dataclass
class SlaModelBundle:
    model: Optional[Any]
    scaler: Optional[Any]
    loaded: bool
    model_version: str
    model_source: str


class SlaModelLoader:
    def __init__(self, cfg: SlaAssuranceConfig) -> None:
        self.cfg = cfg

    def load(self) -> SlaModelBundle:
        model = None
        model_source = "heuristic"
        discovered_version = ""

        scaler = None
        if os.path.exists(self.cfg.scaler_path):
            try:
                scaler = joblib.load(self.cfg.scaler_path)
                logger.info("Loaded SLA scaler from %s", self.cfg.scaler_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not load SLA scaler: %s", exc)
        else:
            logger.warning("SLA scaler not found at %s", self.cfg.scaler_path)

        if self.cfg.model_path and os.path.exists(self.cfg.model_path):
            model = self._load_xgb_classifier(self.cfg.model_path)
            if model is not None:
                model_source = self.cfg.model_path

        if model is None:
            model, model_source, discovered_version = self._load_from_local_registry(
                model_name=self.cfg.model_name,
                db_path=self.cfg.mlflow_db_path,
                mlruns_dir=self.cfg.mlruns_dir,
            )

        model_version = self.cfg.model_version.strip() or discovered_version or "heuristic"
        loaded = model is not None and scaler is not None

        if loaded:
            logger.info("SLA model ready (version=%s source=%s)", model_version, model_source)
        else:
            logger.warning("SLA model unavailable, runtime will use heuristic risk scoring")

        return SlaModelBundle(
            model=model,
            scaler=scaler,
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

            pattern = os.path.join(mlruns_dir, "*", "models", model_id, "artifacts", "model.ubj")
            matches = glob.glob(pattern)
            if not matches:
                logger.warning("Could not resolve local artifact for %s (pattern=%s)", model_name, pattern)
                return None, "heuristic", f"{model_name}:v{version}"

            model_path = matches[0]
            model = self._load_xgb_classifier(model_path)
            if model is None:
                return None, "heuristic", f"{model_name}:v{version}"

            logger.info("Loaded %s from local registry artifact %s", model_name, model_path)
            return model, model_path, f"{model_name}:v{version}"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed loading SLA model from registry metadata: %s", exc)
            return None, "heuristic", ""

    @staticmethod
    def _load_xgb_classifier(path: str) -> Optional[xgb.XGBClassifier]:
        try:
            model = xgb.XGBClassifier()
            model.load_model(path)
            logger.info("Loaded XGBoost classifier from %s", path)
            return model
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load XGBoost classifier from %s: %s", path, exc)
            return None
