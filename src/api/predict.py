"""Prediction helpers for the Smart Slice 5G/6G API."""

import numpy as np
import torch

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

congestion_6g_alert_THRESHOLD = 0.75  # normalised CPU


# =============================================================================
# Congestion (6G LSTM)
# =============================================================================
def predict_congestion_6g(model: torch.nn.Module, data: Congestion6GInput) -> Congestion6GOutput:
    """Run inference with the LSTM congestion model.

    Args:
        model:  Loaded PyTorch LSTM model.
        data:   Congestion6GInput with 24-step cpu and bandwidth sequences.

    Returns:
        Congestion6GOutput with forecast value and boolean alert flag.
    """
    # Build (1, 24, 2) tensor from the two 24-element lists
    seq = list(zip(data.cpu_sequence, data.bandwidth_sequence))
    tensor = torch.tensor([seq], dtype=torch.float32)  # (1, 24, 2)

    model.eval()
    with torch.no_grad():
        prediction = model(tensor).squeeze().item()

    alert = prediction > congestion_6g_alert_THRESHOLD
    return Congestion6GOutput(
        forecast_cpu_next_5min=float(prediction),
        congestion_6g_alert=bool(alert),
    )


# =============================================================================
# Slice selection (stub)
# =============================================================================
def predict_slice(model, data: SliceInput) -> SliceOutput:
    """Stub: returns a fixed slice recommendation until the model is trained."""
    return SliceOutput(recommended_slice="eMBB", confidence=0.5)


# =============================================================================
# SLA adherence (5G XGBoost – Model B)
# =============================================================================
def predict_sla_5g(model, scaler, data: SLA5GInput) -> SLA5GOutput:
    """Run inference with the SLA adherence XGBoost model.

    Args:
        model:   Loaded XGBoost model.
        scaler:  Fitted StandardScaler for the 5 input features.
        data:    SLA5GInput with the 5 features.

    Returns:
        SLA5GOutput with prediction, probability, risk level, and action.
    """
    features = np.array(
        [[data.packet_loss_rate, data.packet_delay, data.smart_city_home, data.iot_devices, data.public_safety]]
    )

    features_scaled = scaler.transform(features)

    pred = int(model.predict(features_scaled)[0])
    prob = float(model.predict_proba(features_scaled)[0][1])

    if prob >= 0.70:
        risk = "LOW"
        action = "Maintain session on assigned slice."
    elif prob >= 0.40:
        risk = "MEDIUM"
        action = "Monitor — prepare fallback policy or preventive scaling."
    else:
        risk = "HIGH"
        action = "ALERT — Reassign session or trigger immediate scaling via A1 policy."

    return SLA5GOutput(
        sla_prediction=pred,
        sla_probability=round(prob, 4),
        risk_level=risk,
        recommended_action=action,
    )


# =============================================================================
# Anomaly detection (stub)
# =============================================================================
def predict_anomaly(model, data: AnomalyInput) -> AnomalyOutput:
    """Stub: returns a fixed anomaly result until the model is trained."""
    return AnomalyOutput(is_anomaly=False, anomaly_score=0.0)
