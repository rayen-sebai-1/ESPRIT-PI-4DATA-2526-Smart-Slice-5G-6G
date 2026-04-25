# Ingestion Tier

The ingestion tier receives simulator telemetry, converts heterogeneous payloads into the shared canonical event model, and forwards the results to Redis, Kafka, and InfluxDB consumers.

## Components

- `adapter-ves/`: FastAPI ingress for VES-like telemetry
- `adapter-netconf/`: FastAPI ingress for NETCONF-like telemetry
- `normalizer/`: background worker that produces canonical telemetry
- `telemetry-exporter/`: background worker that writes telemetry and fault data to InfluxDB
- `shared/`: shared config, Redis helpers, and data models used across tiers

## Runtime Responsibilities

### `adapter-ves`

- host port: `7001`
- routes:
  - `GET /health`
  - `GET /metrics`
  - `POST /events`
- publishes accepted payloads to Redis stream `stream:raw.ves`
- rejects a simulated malformed share of traffic at roughly `5%`

### `adapter-netconf`

- host port: `7002`
- routes:
  - `GET /health`
  - `GET /metrics`
  - `POST /telemetry`
- flattens hierarchical payloads into section records
- publishes records to Redis stream `stream:raw.netconf`
- deliberately injects a small schema mismatch by renaming `forwardingLatencyMs` to `delay_ms` in roughly `3%` of payloads

### `normalizer`

- consumes `stream:raw.ves` and `stream:raw.netconf`
- maps both protocols into the canonical schema defined in `shared/models.py`
- writes canonical events to `stream:norm.telemetry`
- stores latest per-entity state in `entity:{entity_id}`
- mirrors canonical events to Kafka topic `telemetry-norm`
- remaps the NETCONF `delay_ms` mismatch back to `forwardingLatencyMs`

### `telemetry-exporter`

- consumes Kafka topic `telemetry-norm`
- writes telemetry points to InfluxDB measurement `telemetry`
- polls Redis hash `faults:active`
- writes fault summaries and active-fault details to InfluxDB measurement `faults`

## Data Contracts

Primary Redis streams:

- `stream:raw.ves`
- `stream:raw.netconf`
- `stream:norm.telemetry`
- `stream:fault.events`

Primary Redis hashes:

- `entity:{entity_id}`
- `faults:active`

Primary Kafka topic:

- `telemetry-norm`

Primary InfluxDB measurements:

- `telemetry`
- `faults`

## Canonical Event Model

`shared/models.py` defines the canonical event schema used by ingestion, simulation, AIOps, and API services.

Core fields include:

- identity: event, site, node, and entity identifiers
- topology: `domain`, optional `sliceId`, optional `sliceType`
- KPI payload: normalized metrics from the source adapters
- derived fields such as `congestionScore`, `healthScore`, and `misroutingScore`
- scenario and severity metadata when faults are active

## Key Configuration

Shared config is loaded from `shared/config.py`, including:

- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_DB`
- `STREAM_MAXLEN`
- `SERVICE_NAME`
- `SITE_ID`
- `VES_ADAPTER_URL`
- `NETCONF_ADAPTER_URL`
- `FAULT_ENGINE_URL`

Component-specific variables:

- `normalizer`: `KAFKA_BROKER`, `KAFKA_TOPIC`
- `telemetry-exporter`: `KAFKA_BROKER`, `KAFKA_TOPIC`, `INFLUXDB_URL`, `INFLUXDB_TOKEN`, `INFLUXDB_ORG`, `INFLUXDB_BUCKET`

## Run Only This Tier

```bash
cd neuroslice-platform/infrastructure
docker compose up --build adapter-ves adapter-netconf normalizer telemetry-exporter
```

Recommended dependencies:

- `redis`
- `kafka`
- `influxdb`

## Current Limits

- The adapters expose Prometheus-format `/metrics`, but no Prometheus container is started by the integrated Compose stack.
- `telemetry-exporter` is a worker only and does not expose an HTTP API.
- The shared package is also imported by simulation, AIOps, and API services, so schema changes here affect multiple tiers.
