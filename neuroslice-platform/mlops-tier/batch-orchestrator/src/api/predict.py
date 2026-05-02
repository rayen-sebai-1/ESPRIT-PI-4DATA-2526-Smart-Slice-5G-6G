"""Prediction helpers for the Smart Slice 5G/6G API."""

import numpy as np
import torch

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

congestion_6g_alert_THRESHOLD = 0.75  # normalised CPU


# =============================================================================
# Congestion (6G LSTM)
# =============================================================================
def predict_congestion_6g(
    model: torch.nn.Module, data: Congestion6GInput
) -> Congestion6GOutput:
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
# Congestion (5G LSTM)
# =============================================================================
def predict_congestion_5g(
    model: torch.nn.Module, preprocessor, data: Congestion5GInput
) -> Congestion5GOutput:
    """Run inference with the 5G LSTM congestion model."""
    import numpy as np

    # sequence is expected to be a 30x7 list
    seq_array = np.array(data.sequence)
    if seq_array.shape != (30, 7):
        raise ValueError(f"Expected sequence of shape (30, 7), got {seq_array.shape}")

    # Scale features
    # Note: data in sequence needs to have same order as preprocessor.feature_cols
    # ['cpu_util_pct', 'mem_util_pct', 'bw_util_pct', 'active_users', 'queue_len', 'hour', 'slice_type_encoded']
    scaled_seq = preprocessor.scaler.transform(seq_array)

    # Build batch (1, 30, 7)
    tensor = torch.tensor([scaled_seq], dtype=torch.float32)
    device = next(model.parameters()).device
    tensor = tensor.to(device)

    model.eval()
    with torch.no_grad():
        output = model(tensor)
        probability = torch.sigmoid(output).item()

    # Optimal threshold based on findings.
    # For now, keep 0.5 as API default.
    # The actual API threshold could be injected alongside model, but let's assume 0.5.
    alert = probability > 0.5

    return Congestion5GOutput(
        congestion_probability=probability,
        congestion_alert=alert,
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
        [
            [
                data.packet_loss_rate,
                data.packet_delay,
                data.smart_city_home,
                data.iot_devices,
                data.public_safety,
            ]
        ]
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
# Slice-Type prediction (5G LightGBM – multiclass)
# =============================================================================
def predict_slice_type_5g(
    model, label_encoder, data: SliceType5GInput
) -> SliceType5GOutput:
    """Run inference with the Slice-Type-5G LightGBM multiclass model.

    Args:
        model:         Loaded LightGBM classifier.
        label_encoder: Fitted LabelEncoder (maps 0/1/2 → eMBB/mMTC/URLLC).
        data:          SliceType5GInput with 6 features.

    Returns:
        SliceType5GOutput with predicted slice, label, confidence, and full probability dict.
    """
    # Build (1, 6) array — must match preprocessing column order:
    # LTE/5g Category, Packet Loss Rate, Packet delay, Smartphone, IoT Devices, GBR
    features = np.array(
        [
            [
                data.lte_5g_category,
                data.packet_loss_rate,
                data.packet_delay,
                data.smartphone,
                data.iot_devices,
                data.gbr,
            ]
        ]
    )

    proba = model.predict_proba(features)[0]  # shape (3,)
    label = int(np.argmax(proba))
    predicted_slice = str(label_encoder.inverse_transform([label])[0])
    confidence = float(proba[label])

    class_names = list(label_encoder.classes_)
    all_probs = {cls: round(float(p), 4) for cls, p in zip(class_names, proba)}

    return SliceType5GOutput(
        predicted_slice=predicted_slice,
        slice_label=label,
        confidence=round(confidence, 4),
        all_probabilities=all_probs,
    )


# =============================================================================
# Slice-Type prediction (6G XGBoost – multiclass)
# =============================================================================
def predict_slice_type_6g(
    model, label_encoder, data: SliceType6GInput
) -> SliceType6GOutput:
    """Run inference with the Slice-Type-6G XGBoost multiclass model.

    Args:
        model:         Loaded XGBoost classifier.
        label_encoder: Fitted LabelEncoder.
        data:          SliceType6GInput with 10 features.

    Returns:
        SliceType6GOutput with predicted slice, label, confidence, and full probability dict.
    """
    mob_val = 1.0 if data.required_mobility.lower() == "yes" else 0.0
    conn_val = 1.0 if data.required_connectivity.lower() == "yes" else 0.0

    # Build (1, 10) array
    features = np.array(
        [
            [
                data.packet_loss_budget,
                data.latency_budget_ns,
                data.jitter_budget_ns,
                data.data_rate_budget_gbps,
                mob_val,
                conn_val,
                data.slice_available_transfer_rate_gbps,
                data.slice_latency_ns,
                data.slice_packet_loss,
                data.slice_jitter_ns,
            ]
        ]
    )

    proba = model.predict_proba(features)[0]  # shape (5,)
    label = int(np.argmax(proba))
    predicted_slice = str(label_encoder.inverse_transform([label])[0])
    confidence = float(proba[label])

    class_names = list(label_encoder.classes_)
    all_probs = {str(cls): round(float(p), 4) for cls, p in zip(class_names, proba)}

    return SliceType6GOutput(
        predicted_slice=predicted_slice,
        slice_label=label,
        confidence=round(confidence, 4),
        all_probabilities=all_probs,
    )


# =============================================================================
# SLA adherence (6G XGBoost — temporal QoS + context)
# =============================================================================
def predict_sla_6g(model, scaler, data: SLA6GInput) -> SLA6GOutput:
    """Run inference with the SLA-6G adherence XGBoost model.

    Args:
        model:   Loaded XGBoost model (sla-xgboost-6g).
        scaler:  Fitted StandardScaler for the 14 input features.
        data:    SLA6GInput with 14 temporal QoS + context features.

    Returns:
        SLA6GOutput with prediction, probability, risk level, and action.

    Feature order must exactly match the preprocessing pipeline:
        Slice Latency (ns)_lag1, _rolling_mean, _rolling_std
        Slice Packet Loss_lag1, _rolling_mean, _rolling_std
        Slice Jitter (ns)_lag1, _rolling_mean, _rolling_std
        Slice Type Encoded, Mobility Encoded, Connectivity Encoded,
        Handover Encoded, Slice Available Transfer Rate (Gbps)
    """
    features = np.array(
        [
            [
                data.slice_latency_lag1,
                data.slice_latency_rolling_mean,
                data.slice_latency_rolling_std,
                data.slice_packet_loss_lag1,
                data.slice_packet_loss_rolling_mean,
                data.slice_packet_loss_rolling_std,
                data.slice_jitter_lag1,
                data.slice_jitter_rolling_mean,
                data.slice_jitter_rolling_std,
                data.slice_type_encoded,
                data.mobility_encoded,
                data.connectivity_encoded,
                data.handover_encoded,
                data.slice_available_transfer_rate_gbps,
            ]
        ]
    )

    features_scaled = scaler.transform(features)

    pred = int(model.predict(features_scaled)[0])
    prob = float(model.predict_proba(features_scaled)[0][1])

    if prob >= 0.70:
        risk = "LOW"
        action = "Maintain session on assigned 6G slice."
    elif prob >= 0.40:
        risk = "MEDIUM"
        action = (
            "Monitor — prepare fallback policy or preventive scaling on near-RT RIC."
        )
    else:
        risk = "HIGH"
        action = "ALERT — Reassign session or trigger immediate scaling via A1 policy (6G xApp)."

    return SLA6GOutput(
        sla_prediction=pred,
        sla_probability=round(prob, 4),
        risk_level=risk,
        recommended_action=action,
    )
