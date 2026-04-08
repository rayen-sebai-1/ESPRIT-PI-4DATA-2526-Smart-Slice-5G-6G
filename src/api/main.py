"""FastAPI application for the Smart Slice 5G/6G MLOps pipeline."""

import joblib

import mlflow.pytorch
import mlflow.xgboost
from fastapi import FastAPI, HTTPException

from src.api.predict import predict_anomaly, predict_congestion_6g, predict_sla_5g, predict_slice
from src.api.schemas import (
    AnomalyInput,
    AnomalyOutput,
    Congestion6GInput,
    Congestion6GOutput,
    SLA5GInput,
    SLA5GOutput,
    SliceInput,
    SliceOutput,
)

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Smart Slice 5G/6G Prediction API",
    description=(
        "MLOps API exposing congestion forecasting, slice selection, "
        "and anomaly detection endpoints for 5G/6G network slicing."
    ),
    version="1.0.0",
)

# Model holders (populated at startup)
_models: dict = {}

CONGESTION_MODEL_URI = "models:/congestion-lstm-6g/Production"
SLICE_MODEL_URI = "models:/slice-selection/Production"
SLA_MODEL_URI = "models:/sla-xgboost-5g/Production"
SLA_SCALER_PATH = "data/processed/scaler_sla_5g.pkl"
ANOMALY_MODEL_URI = "models:/anomaly-detection/Production"


# ---------------------------------------------------------------------------
# Lifecycle events
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def load_models() -> None:
    """Load registered MLflow models into memory at startup."""
    # Congestion model (required)
    try:
        _models["congestion_6g"] = mlflow.pytorch.load_model(CONGESTION_MODEL_URI)
        _models["congestion_6g"].eval()
        print(f"[INFO] Loaded congestion model from '{CONGESTION_MODEL_URI}'.")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Could not load congestion model: {exc}")

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
        import os

        if os.path.exists(SLA_SCALER_PATH):
            _models["sla_5g_scaler"] = joblib.load(SLA_SCALER_PATH)
            print(f"[INFO] Loaded SLA scaler from '{SLA_SCALER_PATH}'.")
        else:
            _models["sla_5g_scaler"] = None
            print(f"[WARN] SLA scaler not found at '{SLA_SCALER_PATH}'.")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Could not load SLA scaler: {exc}")
        _models["sla_5g_scaler"] = None

    # Anomaly-detection model (optional – stub used until trained)
    try:
        _models["anomaly"] = mlflow.pyfunc.load_model(ANOMALY_MODEL_URI)
        print(f"[INFO] Loaded anomaly model from '{ANOMALY_MODEL_URI}'.")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Anomaly model not found – stub will be used: {exc}")
        _models["anomaly"] = None


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
        raise HTTPException(status_code=503, detail="Congestion model not loaded.")
    return predict_congestion_6g(model, payload)


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


@app.post("/predict/anomaly", response_model=AnomalyOutput, tags=["Prediction"])
async def predict_anomaly_endpoint(payload: AnomalyInput) -> AnomalyOutput:
    """Detect anomalies in network KPIs."""
    return predict_anomaly(_models.get("anomaly"), payload)
