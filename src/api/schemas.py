"""Pydantic schemas for the Smart Slice 5G/6G prediction API."""

from typing import List

from pydantic import BaseModel, Field


# =============================================================================
# Congestion (6G LSTM)
# =============================================================================
class Congestion6GInput(BaseModel):
    """Input payload for the congestion forecasting endpoint."""

    cpu_sequence: List[float] = Field(
        ...,
        min_length=24,
        max_length=24,
        description="Normalised CPU-utilisation values for the last 24 time steps.",
    )
    bandwidth_sequence: List[float] = Field(
        ...,
        min_length=24,
        max_length=24,
        description="Normalised bandwidth values for the last 24 time steps.",
    )


class Congestion6GOutput(BaseModel):
    """Output payload for the congestion forecasting endpoint."""

    forecast_cpu_next_5min: float = Field(
        ...,
        description="Predicted normalised CPU utilisation for the next 5-minute window.",
    )
    congestion_6g_alert: bool = Field(
        ...,
        description="True when the forecast exceeds the 0.75 normalised-CPU threshold.",
    )

# =============================================================================
# Congestion (5G LSTM)
# =============================================================================
class Congestion5GInput(BaseModel):
    """Input payload for the 5G congestion forecasting endpoint."""

    sequence: List[List[float]] = Field(
        ...,
        description="List of 30 time steps. Each time step must have 7 features: [cpu_util_pct, mem_util_pct, bw_util_pct, active_users, queue_len, hour, slice_type_encoded].",
    )


class Congestion5GOutput(BaseModel):
    """Output payload for the 5G congestion forecasting endpoint."""

    congestion_probability: float = Field(..., description="Probability of congestion.")
    congestion_alert: bool = Field(..., description="True if congestion is predicted.")


# =============================================================================
# Slice selection (5G / 6G XGBoost)
# =============================================================================
class SliceInput(BaseModel):
    """Input features for the slice-selection model."""

    cpu_utilization: float = Field(..., ge=0.0, le=1.0)
    memory_utilization: float = Field(..., ge=0.0, le=1.0)
    bandwidth_mbps: float = Field(..., ge=0.0)
    active_users: int = Field(..., ge=0)
    queue_length: int = Field(..., ge=0)
    latency_ms: float = Field(..., ge=0.0)


class SliceOutput(BaseModel):
    """Output of the slice-selection model."""

    recommended_slice: str = Field(..., description="One of: eMBB, URLLC, mMTC")
    confidence: float = Field(..., ge=0.0, le=1.0)


# =============================================================================
# SLA adherence (5G XGBoost – Model B)
# =============================================================================
class SLA5GInput(BaseModel):
    """Input features for the SLA adherence model."""

    packet_loss_rate: float = Field(..., ge=0.0, description="Packet loss rate measured via E2 interface.")
    packet_delay: float = Field(..., ge=0.0, description="Packet delay in ms measured via E2 interface.")
    smart_city_home: int = Field(..., ge=0, le=1, description="1 if Smart City & Home service, else 0.")
    iot_devices: int = Field(..., ge=0, le=1, description="1 if IoT device, else 0.")
    public_safety: int = Field(..., ge=0, le=1, description="1 if Public Safety service, else 0.")


class SLA5GOutput(BaseModel):
    """Output of the SLA adherence model."""

    sla_prediction: int = Field(..., description="0 = SLA not met, 1 = SLA met.")
    sla_probability: float = Field(..., ge=0.0, le=1.0, description="P(sla_met=1) — confidence score.")
    risk_level: str = Field(..., description="Risk level: LOW, MEDIUM, or HIGH.")
    recommended_action: str = Field(..., description="Recommended action based on risk level.")


# =============================================================================
# Slice-Type prediction (5G LightGBM – multiclass)
# =============================================================================
class SliceType5GInput(BaseModel):
    """Input features for the Slice-Type-5G LightGBM classifier.

    Feature order must match the preprocessing pipeline:
    LTE/5g Category, Packet Loss Rate, Packet delay, Smartphone, IoT Devices, GBR.
    """

    lte_5g_category: float = Field(..., description="LTE/5G category indicator (numeric).")
    packet_loss_rate: float = Field(..., ge=0.0, description="Packet loss rate.")
    packet_delay: float = Field(..., ge=0.0, description="Packet delay in ms.")
    smartphone: int = Field(..., ge=0, le=1, description="1 if Smartphone service, else 0.")
    iot_devices: int = Field(..., ge=0, le=1, description="1 if IoT Devices service, else 0.")
    gbr: float = Field(..., ge=0.0, description="Guaranteed Bit Rate value.")


class SliceType5GOutput(BaseModel):
    """Output of the Slice-Type-5G LightGBM classifier."""

    predicted_slice: str = Field(..., description="Predicted slice type: eMBB, mMTC, or URLLC.")
    slice_label: int = Field(..., description="Encoded label: 0=eMBB, 1=mMTC, 2=URLLC.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Max class probability.")
    all_probabilities: dict = Field(
        ..., description="Class probabilities as {'eMBB': p, 'mMTC': p, 'URLLC': p}."
    )


# =============================================================================
# Slice-Type prediction (6G XGBoost – multiclass)
# =============================================================================
class SliceType6GInput(BaseModel):
    """Input features for the Slice-Type-6G XGBoost classifier.

    Feature order must match the preprocessing pipeline exactly.
    """

    packet_loss_budget: float = Field(..., description="Packet Loss Budget.")
    latency_budget_ns: float = Field(..., description="Latency Budget (ns).")
    jitter_budget_ns: float = Field(..., description="Jitter Budget (ns).")
    data_rate_budget_gbps: float = Field(..., description="Data Rate Budget (Gbps).")
    required_mobility: str = Field(..., description="'yes' or 'no'.")
    required_connectivity: str = Field(..., description="'yes' or 'no'.")
    slice_available_transfer_rate_gbps: float = Field(..., description="Slice Available Transfer Rate (Gbps).")
    slice_latency_ns: float = Field(..., description="Slice Latency (ns).")
    slice_packet_loss: float = Field(..., description="Slice Packet Loss.")
    slice_jitter_ns: float = Field(..., description="Slice Jitter (ns).")


class SliceType6GOutput(BaseModel):
    """Output of the Slice-Type-6G XGBoost classifier."""

    predicted_slice: str = Field(..., description="Predicted slice type (e.g. mURLLC, feMBB, etc.).")
    slice_label: int = Field(..., description="Encoded numeric label.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Max class probability.")
    all_probabilities: dict = Field(
        ..., description="Probabilities for all 5 classes."
    )


# =============================================================================
# SLA adherence (6G XGBoost — temporal QoS + context, no-leak)
# =============================================================================
class SLA6GInput(BaseModel):
    """Input features for the SLA-6G adherence model.

    14 features: 9 temporal QoS (lag-1, rolling-mean, rolling-std for
    Latency, Packet Loss, Jitter) + 5 context features.
    All temporal features are past-session measurements (shift-1), ensuring
    no same-row leakage when deployed as a Near-RT RIC xApp.
    """

    # Temporal QoS — Slice Latency (ns)
    slice_latency_lag1: float = Field(..., description="Latency of previous session (ns).")
    slice_latency_rolling_mean: float = Field(..., description="Rolling mean latency over last 5 sessions (ns).")
    slice_latency_rolling_std: float = Field(..., ge=0.0, description="Rolling std of latency over last 5 sessions (ns).")

    # Temporal QoS — Slice Packet Loss
    slice_packet_loss_lag1: float = Field(..., ge=0.0, description="Packet loss of previous session.")
    slice_packet_loss_rolling_mean: float = Field(..., ge=0.0, description="Rolling mean packet loss over last 5 sessions.")
    slice_packet_loss_rolling_std: float = Field(..., ge=0.0, description="Rolling std of packet loss over last 5 sessions.")

    # Temporal QoS — Slice Jitter (ns)
    slice_jitter_lag1: float = Field(..., description="Jitter of previous session (ns).")
    slice_jitter_rolling_mean: float = Field(..., description="Rolling mean jitter over last 5 sessions (ns).")
    slice_jitter_rolling_std: float = Field(..., ge=0.0, description="Rolling std of jitter over last 5 sessions (ns).")

    # Context features
    slice_type_encoded: int = Field(..., ge=0, description="Encoded Slice Type (0=ERLLC, 1=feMBB, 2=MBRLLC, 3=mURLLC, 4=umMTC).")
    mobility_encoded: int = Field(..., ge=0, le=1, description="Encoded Required Mobility (0=no, 1=yes).")
    connectivity_encoded: int = Field(..., ge=0, le=1, description="Encoded Required Connectivity (0=no, 1=yes).")
    handover_encoded: int = Field(..., ge=0, le=1, description="Encoded Slice Handover (0=no, 1=yes).")
    slice_available_transfer_rate_gbps: float = Field(..., ge=0.0, description="Slice Available Transfer Rate (Gbps).")


class SLA6GOutput(BaseModel):
    """Output of the SLA-6G adherence model."""

    sla_prediction: int = Field(..., description="0 = SLA not met, 1 = SLA met.")
    sla_probability: float = Field(..., ge=0.0, le=1.0, description="P(sla_met=1) — confidence score.")
    risk_level: str = Field(..., description="Risk level: LOW, MEDIUM, or HIGH.")
    recommended_action: str = Field(..., description="Recommended action based on risk level.")
