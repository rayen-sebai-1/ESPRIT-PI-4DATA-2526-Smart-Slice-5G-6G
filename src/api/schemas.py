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
# Anomaly detection
# =============================================================================
class AnomalyInput(BaseModel):
    """Input features for the anomaly-detection model."""

    cpu_utilization: float = Field(..., ge=0.0, le=1.0)
    memory_utilization: float = Field(..., ge=0.0, le=1.0)
    bandwidth_mbps: float = Field(..., ge=0.0)
    packet_loss: float = Field(..., ge=0.0, le=1.0)
    latency_ms: float = Field(..., ge=0.0)


class AnomalyOutput(BaseModel):
    """Output of the anomaly-detection model."""

    is_anomaly: bool
    anomaly_score: float
