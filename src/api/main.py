"""FastAPI application for the Smart Slice 5G/6G MLOps pipeline."""

import mlflow.pytorch
from fastapi import FastAPI, HTTPException

from src.api.predict import predict_anomaly, predict_congestion, predict_slice
from src.api.schemas import (
    AnomalyInput,
    AnomalyOutput,
    CongestionInput,
    CongestionOutput,
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
ANOMALY_MODEL_URI = "models:/anomaly-detection/Production"


# ---------------------------------------------------------------------------
# Lifecycle events
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def load_models() -> None:
    """Load registered MLflow models into memory at startup."""
    # Congestion model (required)
    try:
        _models["congestion"] = mlflow.pytorch.load_model(CONGESTION_MODEL_URI)
        _models["congestion"].eval()
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


@app.post("/predict/congestion", response_model=CongestionOutput, tags=["Prediction"])
async def predict_congestion_endpoint(payload: CongestionInput) -> CongestionOutput:
    """Forecast CPU utilisation for the next 5-minute window."""
    model = _models.get("congestion")
    if model is None:
        raise HTTPException(status_code=503, detail="Congestion model not loaded.")
    return predict_congestion(model, payload)


@app.post("/predict/slice", response_model=SliceOutput, tags=["Prediction"])
async def predict_slice_endpoint(payload: SliceInput) -> SliceOutput:
    """Recommend the most appropriate network slice."""
    return predict_slice(_models.get("slice"), payload)


@app.post("/predict/anomaly", response_model=AnomalyOutput, tags=["Prediction"])
async def predict_anomaly_endpoint(payload: AnomalyInput) -> AnomalyOutput:
    """Detect anomalies in network KPIs."""
    return predict_anomaly(_models.get("anomaly"), payload)
