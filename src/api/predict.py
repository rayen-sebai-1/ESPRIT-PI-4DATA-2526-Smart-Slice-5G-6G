"""Prediction helpers for the Smart Slice 5G/6G API."""

import torch

from src.api.schemas import (
    AnomalyInput,
    AnomalyOutput,
    CongestionInput,
    CongestionOutput,
    SliceInput,
    SliceOutput,
)

CONGESTION_ALERT_THRESHOLD = 0.75  # normalised CPU


# =============================================================================
# Congestion (6G LSTM)
# =============================================================================
def predict_congestion(model: torch.nn.Module, data: CongestionInput) -> CongestionOutput:
    """Run inference with the LSTM congestion model.

    Args:
        model:  Loaded PyTorch LSTM model.
        data:   CongestionInput with 24-step cpu and bandwidth sequences.

    Returns:
        CongestionOutput with forecast value and boolean alert flag.
    """
    # Build (1, 24, 2) tensor from the two 24-element lists
    seq = list(zip(data.cpu_sequence, data.bandwidth_sequence))
    tensor = torch.tensor([seq], dtype=torch.float32)  # (1, 24, 2)

    model.eval()
    with torch.no_grad():
        prediction = model(tensor).squeeze().item()

    alert = prediction > CONGESTION_ALERT_THRESHOLD
    return CongestionOutput(
        forecast_cpu_next_5min=float(prediction),
        congestion_alert=bool(alert),
    )


# =============================================================================
# Slice selection (stub)
# =============================================================================
def predict_slice(model, data: SliceInput) -> SliceOutput:
    """Stub: returns a fixed slice recommendation until the model is trained."""
    return SliceOutput(recommended_slice="eMBB", confidence=0.5)


# =============================================================================
# Anomaly detection (stub)
# =============================================================================
def predict_anomaly(model, data: AnomalyInput) -> AnomalyOutput:
    """Stub: returns a fixed anomaly result until the model is trained."""
    return AnomalyOutput(is_anomaly=False, anomaly_score=0.0)
