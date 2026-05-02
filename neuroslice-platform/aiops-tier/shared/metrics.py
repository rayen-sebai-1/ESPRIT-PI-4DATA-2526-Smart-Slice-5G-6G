import os
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# AIOps Common Metrics
aiops_events_processed = Counter(
    "neuroslice_aiops_events_processed_total",
    "Total events processed by the AIOps service",
    ["service", "model_name"]
)

aiops_predictions = Counter(
    "neuroslice_aiops_predictions_total",
    "Total predictions made",
    ["service", "model_name", "prediction"]
)

aiops_fallback_mode = Gauge(
    "neuroslice_aiops_fallback_mode",
    "Whether the AIOps service is running in fallback mode (1) or normal mode (0)",
    ["service", "model_name"]
)

aiops_model_loaded = Gauge(
    "neuroslice_aiops_model_loaded",
    "Whether the model is successfully loaded (1) or not (0)",
    ["service", "model_name"]
)

aiops_last_event_timestamp = Gauge(
    "neuroslice_aiops_last_event_timestamp",
    "Timestamp of the last processed event",
    ["service", "model_name"]
)

aiops_inference_latency = Histogram(
    "neuroslice_aiops_inference_latency_seconds",
    "Latency of model inference in seconds",
    ["service", "model_name"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

aiops_service_enabled = Gauge(
    "neuroslice_aiops_service_enabled",
    "Whether the AIOps service is enabled via runtime control (1) or disabled (0)",
    ["service"]
)

def start_metrics_server(port: int = 8000) -> None:
    start_http_server(port)
