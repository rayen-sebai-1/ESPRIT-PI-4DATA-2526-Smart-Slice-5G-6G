# AIOps Tier

The AIOps tier contains the online inference workers that consume normalized telemetry and publish near-real-time congestion, SLA-risk, and slice-classification outputs.

## Implemented Services

This tier currently contains three runtime workers:

- `congestion-detector/`
- `sla-assurance/`
- `slice-classifier/`

There are no additional committed services under `aiops-tier/` in the current workspace.

## Runtime Role

All three workers:

- consume canonical telemetry from `stream:norm.telemetry`
- run as background workers, not HTTP APIs
- publish results to Redis Streams
- store latest inference state in Redis hashes
- enrich the existing `entity:{entityId}` hashes for fast reads by `api-bff-service`
- optionally publish to Kafka and InfluxDB
- read model artifacts from `/mlops`, mounted from `../mlops-tier/batch-orchestrator`

## Output Contracts

### `congestion-detector`

- input stream: `stream:norm.telemetry`
- output Redis stream: `events.anomaly`
- latest-state hash prefix: `aiops:congestion:{entityId}`
- Kafka topic: `events.anomaly`
- InfluxDB measurement: `aiops_congestion`
- key threshold env: `CONGESTION_THRESHOLD`
- model inputs:
  - `/mlops/models/congestion_5g_lstm_traced.pt`
  - `/mlops/data/processed/preprocessor_congestion_5g.pkl`

If the model or preprocessor is missing, the service falls back to heuristic scoring.

### `sla-assurance`

- input stream: `stream:norm.telemetry`
- output Redis stream: `events.sla`
- latest-state hash prefix: `aiops:sla:{entityId}`
- Kafka topic: `events.sla`
- InfluxDB measurement: `aiops_sla`
- key threshold env: `SLA_RISK_THRESHOLD`
- model discovery:
  - explicit `SLA_MODEL_PATH`, if provided
  - otherwise local MLflow metadata from `/mlops/mlflow.db` and `/mlops/mlruns`
- scaler path:
  - `/mlops/data/processed/scaler_sla_5g.pkl`

If the model or scaler is unavailable, the service falls back to heuristic risk scoring.

### `slice-classifier`

- input stream: `stream:norm.telemetry`
- output Redis stream: `events.slice.classification`
- latest-state hash prefix: `aiops:slice_classification:{entityId}`
- Kafka topic: `events.slice.classification`
- InfluxDB measurement: `aiops_slice_classification`
- key threshold env: `SLICE_MISMATCH_CONFIDENCE_THRESHOLD`
- model discovery:
  - explicit `SLICE_MODEL_PATH`, if provided
  - otherwise local MLflow metadata from `/mlops/mlflow.db` and `/mlops/mlruns`
- label encoder path:
  - `/mlops/data/processed/label_encoder_slice_type_5g.pkl`

If the model or encoder is unavailable, the service falls back to heuristic classification.

## Data Flow

```text
stream:norm.telemetry
  -> congestion-detector  -> events.anomaly
  -> sla-assurance        -> events.sla
  -> slice-classifier     -> events.slice.classification

Outputs also go to:
  -> Redis latest-state hashes under aiops:*
  -> Redis entity:{entityId} enrichment fields
  -> Kafka topics
  -> InfluxDB measurements
```

Current downstream consumers include:

- `api-dashboard-tier/api-bff-service`
- Grafana via InfluxDB
- future control and agentic-ai tiers

## Key Environment Variables

Common variables across all three services:

- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_DB`
- `STREAM_MAXLEN`
- `INPUT_STREAM`
- `CONSUMER_GROUP`
- `CONSUMER_NAME`
- `READ_COUNT`
- `BLOCK_MS`
- `OUTPUT_STREAM`
- `KAFKA_ENABLED`
- `KAFKA_BROKER`
- `KAFKA_TOPIC`
- `INFLUXDB_ENABLED`
- `INFLUXDB_URL`
- `INFLUXDB_TOKEN`
- `INFLUXDB_ORG`
- `INFLUXDB_BUCKET`
- `INFLUX_MEASUREMENT`
- `STATE_PREFIX`
- `STATE_TTL_SEC`
- `SITE_ID`

Service-specific variables:

- `congestion-detector`
  - `CONGESTION_MODEL_PATH`
  - `CONGESTION_PREPROCESSOR_PATH`
  - `CONGESTION_MODEL_VERSION`
  - `CONGESTION_SEQUENCE_LENGTH`
  - `CONGESTION_THRESHOLD`
- `sla-assurance`
  - `SLA_MODEL_NAME`
  - `SLA_MODEL_PATH`
  - `SLA_MODEL_VERSION`
  - `MLFLOW_DB_PATH`
  - `MLRUNS_DIR`
  - `SLA_SCALER_PATH`
  - `SLA_RISK_THRESHOLD`
- `slice-classifier`
  - `SLICE_MODEL_NAME`
  - `SLICE_MODEL_PATH`
  - `SLICE_MODEL_VERSION`
  - `MLFLOW_DB_PATH`
  - `MLRUNS_DIR`
  - `SLICE_LABEL_ENCODER_PATH`
  - `SLICE_MISMATCH_CONFIDENCE_THRESHOLD`

## Running The Tier

The authoritative runtime path is the top-level Compose file:

```bash
cd neuroslice-platform/infrastructure
docker compose up --build congestion-detector sla-assurance slice-classifier
```

Typical required dependencies:

- `redis`
- `kafka`
- `influxdb`
- `normalizer`
- the read-only mount `../mlops-tier/batch-orchestrator:/mlops`

## Current Repository Note

Earlier documents referenced `misrouting-detector/` and `shared-alibi-sidecar/`. Those directories are not present in the current repo snapshot.

## Folder Map

```text
aiops-tier/
|-- README.md
|-- congestion-detector/
|-- sla-assurance/
`-- slice-classifier/
```
