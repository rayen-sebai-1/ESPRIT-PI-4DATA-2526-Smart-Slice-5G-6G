"""FastAPI application for the Smart Slice 5G/6G MLOps pipeline."""

import os

import joblib

import mlflow
import mlflow.pytorch
import mlflow.xgboost
from fastapi import FastAPI, HTTPException

from src.api.predict import (
    predict_congestion_5g,
    predict_congestion_6g,
    predict_sla_5g,
    predict_sla_6g,
    predict_slice,
    predict_slice_type_5g,
    predict_slice_type_6g,
)
from src.api.schemas import (
    Congestion6GInput,
    Congestion6GOutput,
    Congestion5GInput,
    Congestion5GOutput,
    SLA5GInput,
    SLA5GOutput,
    SLA6GInput,
    SLA6GOutput,
    SliceInput,
    SliceOutput,
    SliceType5GInput,
    SliceType5GOutput,
    SliceType6GInput,
    SliceType6GOutput,
)
from src.models.lifecycle import configure_mlflow_tracking

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Smart Slice 5G/6G Prediction API",
    description=(
        "MLOps API exposing congestion forecasting, slice selection, "
        "and SLA/slice-type prediction endpoints for 5G/6G network slicing."
    ),
    version="1.0.0",
)

# Model holders (populated at startup)
_models: dict = {}

MLFLOW_TRACKING_URI = configure_mlflow_tracking()
CONGESTION_MODEL_URI = "models:/congestion-lstm-6g/Production"
CONGESTION_5G_MODEL_PATH = "models/congestion_5g_lstm_traced.pt"
CONGESTION_5G_PREPROCESSOR_PATH = "data/processed/preprocessor_congestion_5g.pkl"
SLICE_MODEL_URI = "models:/slice-selection/Production"
SLA_MODEL_URI = "models:/sla-xgboost-5g/Production"
SLA_SCALER_PATH = "data/processed/scaler_sla_5g.pkl"
SLICE_TYPE_5G_MODEL_URI = "models:/slice-type-lgbm-5g/Production"
SLICE_TYPE_5G_LABEL_ENCODER_PATH = "data/processed/label_encoder_slice_type_5g.pkl"
SLICE_TYPE_6G_MODEL_URI = "models:/slice-type-6g/1"
SLICE_TYPE_6G_LABEL_ENCODER_PATH = "data/processed/label_encoder_slice_type_6g.pkl"
SLA_6G_MODEL_URI = "models:/sla-xgboost-6g/Production"
SLA_6G_SCALER_PATH = "data/processed/scaler_sla_6g.pkl"


# ---------------------------------------------------------------------------
# Lifecycle events
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def load_models() -> None:
    """Load registered MLflow models into memory at startup."""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

    # Congestion model (required)
    try:
        _models["congestion_6g"] = mlflow.pytorch.load_model(CONGESTION_MODEL_URI)
        _models["congestion_6g"].eval()
        print(f"[INFO] Loaded congestion model from '{CONGESTION_MODEL_URI}'.")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Could not load congestion model: {exc}")

    # Congestion 5G model
    try:
        import torch
        _models["congestion_5g"] = torch.jit.load(CONGESTION_5G_MODEL_PATH)
        _models["congestion_5g"].eval()
        _models["congestion_5g_preprocessor"] = joblib.load(CONGESTION_5G_PREPROCESSOR_PATH)
        print(f"[INFO] Loaded congestion 5G model from '{CONGESTION_5G_MODEL_PATH}'.")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Could not load congestion 5G model or preprocessor: {exc}")

    # Slice-selection model (optional – stub used until trained)
    try:
        _models["slice"] = mlflow.pyfunc.load_model(SLICE_MODEL_URI)
        print(f"[INFO] Loaded slice model from '{SLICE_MODEL_URI}'.")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Slice model not found – stub will be used: {exc}")
        _models["slice"] = None

    # SLA adherence model (optional – stub used until trained)
    try:
        _models["sla_5g"] = mlflow.xgboost.load_model(SLA_MODEL_URI)
        print(f"[INFO] Loaded SLA model from '{SLA_MODEL_URI}'.")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] SLA model not found – stub will be used: {exc}")
        _models["sla_5g"] = None

    # SLA scaler
    try:
        if os.path.exists(SLA_SCALER_PATH):
            _models["sla_5g_scaler"] = joblib.load(SLA_SCALER_PATH)
            print(f"[INFO] Loaded SLA scaler from '{SLA_SCALER_PATH}'.")
        else:
            _models["sla_5g_scaler"] = None
            print(f"[WARN] SLA scaler not found at '{SLA_SCALER_PATH}'.")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Could not load SLA scaler: {exc}")
        _models["sla_5g_scaler"] = None

    # Slice-Type-5G LightGBM model (optional – stub until trained)
    try:
        _models["slice_type_5g"] = mlflow.lightgbm.load_model(SLICE_TYPE_5G_MODEL_URI)
        print(f"[INFO] Loaded slice-type-5g model from '{SLICE_TYPE_5G_MODEL_URI}'.")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Slice-type-5g model not found – endpoint will return 503: {exc}")
        _models["slice_type_5g"] = None

    # Slice-Type-5G label encoder
    try:
        if os.path.exists(SLICE_TYPE_5G_LABEL_ENCODER_PATH):
            _models["slice_type_5g_encoder"] = joblib.load(SLICE_TYPE_5G_LABEL_ENCODER_PATH)
            print(f"[INFO] Loaded slice-type-5g label encoder from '{SLICE_TYPE_5G_LABEL_ENCODER_PATH}'.")
        else:
            _models["slice_type_5g_encoder"] = None
            print(f"[WARN] Slice-type-5g label encoder not found at '{SLICE_TYPE_5G_LABEL_ENCODER_PATH}'.")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Could not load slice-type-5g label encoder: {exc}")
        _models["slice_type_5g_encoder"] = None

    # Slice-Type-6G model
    try:
        _models["slice_type_6g"] = mlflow.xgboost.load_model(SLICE_TYPE_6G_MODEL_URI)
        print(f"[INFO] Loaded slice-type-6g model from '{SLICE_TYPE_6G_MODEL_URI}'.")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Slice-type-6g model not found – endpoint will return 503: {exc}")
        _models["slice_type_6g"] = None

    # Slice-Type-6G label encoder
    try:
        if os.path.exists(SLICE_TYPE_6G_LABEL_ENCODER_PATH):
            _models["slice_type_6g_encoder"] = joblib.load(SLICE_TYPE_6G_LABEL_ENCODER_PATH)
            print(f"[INFO] Loaded slice-type-6g label encoder from '{SLICE_TYPE_6G_LABEL_ENCODER_PATH}'.")
        else:
            _models["slice_type_6g_encoder"] = None
            print(f"[WARN] Slice-type-6g label encoder not found at '{SLICE_TYPE_6G_LABEL_ENCODER_PATH}'.")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Could not load slice-type-6g label encoder: {exc}")
        _models["slice_type_6g_encoder"] = None

    # SLA-6G adherence model (optional — stub used until trained)
    try:
        _models["sla_6g"] = mlflow.xgboost.load_model(SLA_6G_MODEL_URI)
        print(f"[INFO] Loaded SLA-6G model from '{SLA_6G_MODEL_URI}'.")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] SLA-6G model not found – endpoint will return 503: {exc}")
        _models["sla_6g"] = None

    # SLA-6G scaler
    try:
        if os.path.exists(SLA_6G_SCALER_PATH):
            _models["sla_6g_scaler"] = joblib.load(SLA_6G_SCALER_PATH)
            print(f"[INFO] Loaded SLA-6G scaler from '{SLA_6G_SCALER_PATH}'.")
        else:
            _models["sla_6g_scaler"] = None
            print(f"[WARN] SLA-6G scaler not found at '{SLA_6G_SCALER_PATH}'.")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Could not load SLA-6G scaler: {exc}")
        _models["sla_6g_scaler"] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Operations"])
async def health() -> dict:
    """Health-check endpoint."""
    return {"status": "ok"}


@app.post("/predict/congestion_6g", response_model=Congestion6GOutput, tags=["Prediction"])
async def predict_congestion_6g_endpoint(payload: Congestion6GInput) -> Congestion6GOutput:
    """Forecast CPU utilisation for the next 5-minute window."""
    model = _models.get("congestion_6g")
    if model is None:
        raise HTTPException(status_code=503, detail="Congestion 6G model not loaded.")
    return predict_congestion_6g(model, payload)


@app.post("/predict/congestion_5g", response_model=Congestion5GOutput, tags=["Prediction"])
async def predict_congestion_5g_endpoint(payload: Congestion5GInput) -> Congestion5GOutput:
    """Forecast Congestion probability for the 5G slice."""
    model = _models.get("congestion_5g")
    preprocessor = _models.get("congestion_5g_preprocessor")
    if model is None or preprocessor is None:
        raise HTTPException(status_code=503, detail="Congestion 5G model or preprocessor not loaded.")
    try:
        return predict_congestion_5g(model, preprocessor, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/predict/slice", response_model=SliceOutput, tags=["Prediction"])
async def predict_slice_endpoint(payload: SliceInput) -> SliceOutput:
    """Recommend the most appropriate network slice."""
    return predict_slice(_models.get("slice"), payload)


@app.post("/predict/sla_5g", response_model=SLA5GOutput, tags=["Prediction"])
async def predict_sla_5g_endpoint(payload: SLA5GInput) -> SLA5GOutput:
    """Predict SLA adherence probability for a network session."""
    model = _models.get("sla_5g")
    scaler = _models.get("sla_5g_scaler")
    if model is None or scaler is None:
        raise HTTPException(status_code=503, detail="SLA 5G model or scaler not loaded.")
    return predict_sla_5g(model, scaler, payload)


@app.post("/predict/slice_type_5g", response_model=SliceType5GOutput, tags=["Prediction"])
async def predict_slice_type_5g_endpoint(payload: SliceType5GInput) -> SliceType5GOutput:
    """Predict the most appropriate 5G network slice type (eMBB / mMTC / URLLC)."""
    model = _models.get("slice_type_5g")
    label_encoder = _models.get("slice_type_5g_encoder")
    if model is None or label_encoder is None:
        raise HTTPException(status_code=503, detail="Slice-Type-5G model or label encoder not loaded.")
    return predict_slice_type_5g(model, label_encoder, payload)


@app.post("/predict/slice_type_6g", response_model=SliceType6GOutput, tags=["Prediction"])
async def predict_slice_type_6g_endpoint(payload: SliceType6GInput) -> SliceType6GOutput:
    """Predict the most appropriate 6G network slice type."""
    model = _models.get("slice_type_6g")
    label_encoder = _models.get("slice_type_6g_encoder")
    if model is None or label_encoder is None:
        raise HTTPException(status_code=503, detail="Slice-Type-6G model or label encoder not loaded.")
    return predict_slice_type_6g(model, label_encoder, payload)


@app.post("/predict/sla_6g", response_model=SLA6GOutput, tags=["Prediction"])
async def predict_sla_6g_endpoint(payload: SLA6GInput) -> SLA6GOutput:
    """Predict SLA adherence probability for a 6G network session.

    Uses 14 temporal QoS + context features derived from past-session
    measurements to predict whether the current session will meet its SLA.
    """
    model = _models.get("sla_6g")
    scaler = _models.get("sla_6g_scaler")
    if model is None or scaler is None:
        raise HTTPException(status_code=503, detail="SLA-6G model or scaler not loaded.")
    return predict_sla_6g(model, scaler, payload)
