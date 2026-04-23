# AIOps Tier

Runtime online inference services that consume normalized telemetry and publish near-real-time intelligence for congestion, SLA risk, and slice classification.

## Tier Purpose

This tier transforms `stream:norm.telemetry` events into model outputs that can be consumed by APIs, dashboards, and automation loops.

Main responsibilities:

- Consume canonical events from Redis Streams.
- Load trained artifacts from `mlops-tier/batch-orchestrator`.
- Run low-latency inference with fallback heuristics when artifacts are missing.
- Publish outputs to Redis Streams, Redis state hashes, Kafka topics, and InfluxDB measurements.

## Current Status

Implemented services:

- `congestion-detector`
- `sla-assurance`
- `slice-classifier`

Scaffold-only (not implemented yet):

- `misrouting-detector`
- `shared-alibi-sidecar`

## Runtime Contracts

Input stream for all active services:

- `stream:norm.telemetry`

Output contracts by service:

- `congestion-detector`
- Redis stream: `events.anomaly`
- Redis state key prefix: `aiops:congestion:{entityId}`
- Kafka topic: `events.anomaly`
- Influx measurement: `aiops_congestion`
- Threshold env: `CONGESTION_THRESHOLD`

- `sla-assurance`
- Redis stream: `events.sla`
- Redis state key prefix: `aiops:sla:{entityId}`
- Kafka topic: `events.sla`
- Influx measurement: `aiops_sla`
- Threshold env: `SLA_RISK_THRESHOLD`

- `slice-classifier`
- Redis stream: `events.slice.classification`
- Redis state key prefix: `aiops:slice_classification:{entityId}`
- Kafka topic: `events.slice.classification`
- Influx measurement: `aiops_slice_classification`
- Threshold env: `SLICE_MISMATCH_CONFIDENCE_THRESHOLD`

Each service also enriches entity hashes (`entity:{entityId}`) with the latest AIOps fields for fast API reads.

## Model Loading Strategy

Model loading is resilient by design:

- Congestion service loads TorchScript + preprocessor when available.
- SLA and Slice services load from explicit model paths or discover latest versions from local MLflow metadata (`/mlops/mlflow.db`, `/mlops/mlruns`).
- If required artifacts are missing, services continue with heuristic fallback scoring/classification.

## How It Fits in the Platform

```text
stream:norm.telemetry
  -> congestion-detector -> events.anomaly
  -> sla-assurance       -> events.sla
  -> slice-classifier    -> events.slice.classification

All outputs -> Redis latest-state hashes + Kafka + InfluxDB
```

Consumers of this tier:

- `api-dashboard-tier/api-bff-service`
- Grafana dashboards through InfluxDB
- Future control/automation services

## Running the Tier

Preferred (full stack):

```bash
cd neuroslice-platform/infrastructure
docker compose up --build congestion-detector sla-assurance slice-classifier
```

Typical dependencies needed first:

- `redis`
- `kafka`
- `influxdb`
- `normalizer`
- model artifacts mounted from `../mlops-tier/batch-orchestrator` to `/mlops`

## Folder Map

```text
aiops-tier/
├── congestion-detector/
├── sla-assurance/
├── slice-classifier/
├── misrouting-detector/        # scaffold
└── shared-alibi-sidecar/       # scaffold
```

## Next Implementation Targets

1. Implement `misrouting-detector` to operationalize URLLC path/QoS mismatch detection.
2. Add shared explainability payload contract in `shared-alibi-sidecar`.
3. Add contract tests for stream schema compatibility with `api-bff-service`.
