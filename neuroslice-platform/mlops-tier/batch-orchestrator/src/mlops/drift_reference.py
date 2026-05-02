"""Generate drift reference artifacts for each promoted model.

Produces two files per model under models/promoted/{model_name}/current/:
  - drift_reference.npz        -- numpy array x_ref of shape [n_samples, n_features]
  - drift_feature_schema.json  -- stable schema describing the feature vector

The reference distribution is extracted from the preprocessed training data
(data/processed/*.npz + scaler/preprocessor pickle files).  When training data
is unavailable, the function returns a clear status dict with
status="missing_training_data" instead of crashing the caller.

Integration: called by promote_onnx_artifacts() after successful promotion.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature schemas (must match feature_extractor.py in drift-monitor)
# ---------------------------------------------------------------------------

_FEATURE_SCHEMAS: dict[str, dict[str, Any]] = {
    "congestion_5g": {
        "feature_names": [
            "cpu_util_pct",
            "mem_util_pct",
            "bw_util_pct",
            "active_users",
            "queue_len",
            "hour",
            "slice_type_encoded",
        ],
        "feature_count": 7,
        "preprocessing_artifacts": ["preprocessor_congestion_5g.pkl"],
        "drift_method": "alibi_detect_mmd",
        "p_value_threshold": 0.01,
        "window_size": 500,
    },
    "sla_5g": {
        "feature_names": [
            "packet_loss_pct",
            "packet_delay_ms",
            "smart_city_home",
            "iot_devices",
            "public_safety",
        ],
        "feature_count": 5,
        "preprocessing_artifacts": ["scaler_sla_5g.pkl"],
        "drift_method": "alibi_detect_mmd",
        "p_value_threshold": 0.01,
        "window_size": 500,
    },
    "slice_type_5g": {
        "feature_names": [
            "lte5g_category",
            "packet_loss_pct",
            "packet_delay_ms",
            "smartphone",
            "iot_devices",
            "gbr",
        ],
        "feature_count": 6,
        "preprocessing_artifacts": ["label_encoder_slice_type_5g.pkl"],
        "drift_method": "alibi_detect_mmd",
        "p_value_threshold": 0.01,
        "window_size": 500,
    },
}

MAX_REFERENCE_SAMPLES = 2000


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_drift_reference(
    model_name: str,
    *,
    current_dir: Path,
    data_processed_dir: Path | None = None,
    source_dataset: str | None = None,
    max_samples: int = MAX_REFERENCE_SAMPLES,
) -> dict[str, Any]:
    """Generate drift_reference.npz and drift_feature_schema.json for model_name.

    Args:
        model_name:         One of 'congestion_5g', 'sla_5g', 'slice_type_5g'.
        current_dir:        Path to models/promoted/{model_name}/current/ (write target).
        data_processed_dir: Path to data/processed/ (where NPZ + pickle files live).
        source_dataset:     Optional label for the source dataset.
        max_samples:        Maximum rows to include in the reference sample.

    Returns:
        dict with keys 'status', and optionally 'ref_path', 'schema_path',
        'n_samples', 'n_features', 'message'.
    """
    schema = _FEATURE_SCHEMAS.get(model_name)
    if schema is None:
        return {
            "status": "unsupported_model",
            "message": f"No drift feature schema for model_name='{model_name}'",
        }

    data_dir = _resolve_data_dir(data_processed_dir)
    extractor = _EXTRACTORS.get(model_name)

    if extractor is None:
        return {
            "status": "unsupported_model",
            "message": f"No reference extractor for model_name='{model_name}'",
        }

    result = extractor(model_name, data_dir, max_samples)
    if result["status"] != "ok":
        logger.warning("[%s] Could not extract reference data: %s", model_name, result)
        return result

    x_ref: np.ndarray = result["x_ref"]

    # Write drift_reference.npz
    current_dir.mkdir(parents=True, exist_ok=True)
    ref_path = current_dir / "drift_reference.npz"
    np.savez(ref_path, x_ref=x_ref)

    # Write drift_feature_schema.json
    feature_schema = {
        "model_name": model_name,
        "feature_names": schema["feature_names"],
        "feature_count": schema["feature_count"],
        "source_dataset": source_dataset
        or result.get("source_dataset", "training_data"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "preprocessing_artifacts": schema["preprocessing_artifacts"],
        "reference_sample_count": len(x_ref),
        "drift_method": schema["drift_method"],
        "p_value_threshold": schema["p_value_threshold"],
        "window_size": schema["window_size"],
    }
    schema_path = current_dir / "drift_feature_schema.json"
    schema_path.write_text(json.dumps(feature_schema, indent=2), encoding="utf-8")

    logger.info(
        "[%s] Drift reference generated: n_samples=%d n_features=%d -> %s",
        model_name,
        len(x_ref),
        x_ref.shape[1] if x_ref.ndim > 1 else 0,
        ref_path,
    )

    return {
        "status": "ok",
        "ref_path": str(ref_path),
        "schema_path": str(schema_path),
        "n_samples": len(x_ref),
        "n_features": x_ref.shape[1] if x_ref.ndim > 1 else 0,
    }


# ---------------------------------------------------------------------------
# Per-model extractors
# ---------------------------------------------------------------------------


def _resolve_data_dir(data_processed_dir: Path | None) -> Path:
    if data_processed_dir is not None:
        return Path(data_processed_dir)
    # Try common relative locations from the batch-orchestrator working dir.
    candidates = [
        Path("data/processed"),
        Path("../data/processed"),
        Path(os.environ.get("DATA_PROCESSED_DIR", "data/processed")),
    ]
    for c in candidates:
        if c.is_dir():
            return c.resolve()
    return Path("data/processed")


def _extract_congestion_reference(
    model_name: str,
    data_dir: Path,
    max_samples: int,
) -> dict[str, Any]:
    """Extract unscaled feature rows from congestion_5g_processed.npz.

    The stored arrays are scaled sequences of shape [n_seq, seq_len=30, n_feat=7].
    We inverse-transform the last time-step of each sequence to get raw features.
    """
    npz_path = data_dir / "congestion_5g_processed.npz"
    pkl_path = data_dir / "preprocessor_congestion_5g.pkl"

    if not npz_path.exists():
        return {"status": "missing_training_data", "message": str(npz_path)}

    try:
        data = np.load(npz_path)
        x_train = data["X_train"]  # shape [n_seq, seq_len, n_feat]
    except Exception as exc:  # noqa: BLE001
        return {"status": "load_error", "message": str(exc)}

    # Take last timestep: [n_seq, n_feat]
    if x_train.ndim == 3:
        x_flat = x_train[:, -1, :]
    elif x_train.ndim == 2:
        x_flat = x_train
    else:
        return {"status": "unexpected_shape", "message": str(x_train.shape)}

    # Inverse-transform to get unscaled features.
    if pkl_path.exists():
        try:
            import joblib

            preprocessor = joblib.load(pkl_path)
            scaler = getattr(preprocessor, "scaler", None)
            if scaler is not None:
                x_flat = scaler.inverse_transform(x_flat.astype(np.float64)).astype(
                    np.float32
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[%s] Could not inverse-transform; using scaled features: %s",
                model_name,
                exc,
            )

    x_ref = _sample(x_flat, max_samples)
    return {
        "status": "ok",
        "x_ref": x_ref.astype(np.float32),
        "source_dataset": "congestion_5g_processed.npz/X_train",
    }


def _extract_sla_reference(
    model_name: str,
    data_dir: Path,
    max_samples: int,
) -> dict[str, Any]:
    """Extract unscaled features from sla_5g_processed.npz."""
    npz_path = data_dir / "sla_5g_processed.npz"
    pkl_path = data_dir / "scaler_sla_5g.pkl"

    if not npz_path.exists():
        return {"status": "missing_training_data", "message": str(npz_path)}

    try:
        data = np.load(npz_path)
        x_train = data["X_train"].astype(np.float64)
    except Exception as exc:  # noqa: BLE001
        return {"status": "load_error", "message": str(exc)}

    if pkl_path.exists():
        try:
            import joblib

            scaler = joblib.load(pkl_path)
            x_train = scaler.inverse_transform(x_train).astype(np.float32)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] Could not inverse-transform: %s", model_name, exc)

    x_ref = _sample(x_train, max_samples)
    return {
        "status": "ok",
        "x_ref": x_ref.astype(np.float32),
        "source_dataset": "sla_5g_processed.npz/X_train",
    }


def _extract_slice_type_reference(
    model_name: str,
    data_dir: Path,
    max_samples: int,
) -> dict[str, Any]:
    """Extract features from slice_type_5g_processed.npz (no scaler needed)."""
    npz_path = data_dir / "slice_type_5g_processed.npz"

    if not npz_path.exists():
        return {"status": "missing_training_data", "message": str(npz_path)}

    try:
        data = np.load(npz_path)
        x_train = data["X_train"].astype(np.float32)
    except Exception as exc:  # noqa: BLE001
        return {"status": "load_error", "message": str(exc)}

    x_ref = _sample(x_train, max_samples)
    return {
        "status": "ok",
        "x_ref": x_ref.astype(np.float32),
        "source_dataset": "slice_type_5g_processed.npz/X_train",
    }


_EXTRACTORS = {
    "congestion_5g": _extract_congestion_reference,
    "sla_5g": _extract_sla_reference,
    "slice_type_5g": _extract_slice_type_reference,
}


def _sample(x: np.ndarray, max_samples: int) -> np.ndarray:
    if len(x) <= max_samples:
        return x
    rng = np.random.default_rng(seed=42)
    idx = rng.choice(len(x), size=max_samples, replace=False)
    return x[idx]


# ---------------------------------------------------------------------------
# Standalone CLI helper
# ---------------------------------------------------------------------------


def generate_all_drift_references(
    *,
    promoted_root: Path,
    data_processed_dir: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Generate reference artifacts for all three Scenario B models."""
    results: dict[str, dict[str, Any]] = {}
    for model_name in ("congestion_5g", "sla_5g", "slice_type_5g"):
        current_dir = promoted_root / model_name / "current"
        results[model_name] = generate_drift_reference(
            model_name,
            current_dir=current_dir,
            data_processed_dir=data_processed_dir,
        )
    return results


if __name__ == "__main__":
    import sys

    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("models/promoted")
    data = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    out = generate_all_drift_references(promoted_root=root, data_processed_dir=data)
    for name, r in out.items():
        print(f"{name}: {r}")
