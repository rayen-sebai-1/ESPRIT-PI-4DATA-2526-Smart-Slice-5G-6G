# Ingestion Tier

The ingestion tier receives simulator telemetry, normalizes heterogeneous payloads into a shared canonical event model, and forwards events to Redis, Kafka, and InfluxDB consumers.

## Components

- `adapter-ves/`: FastAPI ingress for VES-like telemetry
- `adapter-netconf/`: FastAPI ingress for NETCONF-like telemetry
- `normalizer/`: background worker that produces canonical telemetry
- `telemetry-exporter/`: background worker that writes telemetry and fault data to InfluxDB
- `shared/`: shared config, Redis helpers, and Pydantic models used across tiers

## Runtime Responsibilities

### `adapter-ves`

- default host port: `7001`
- routes:
  - `GET /health`
  - `GET /metrics`
  - `POST /events`
- publishes accepted payloads to Redis stream `stream:raw.ves`
- intentionally rejects a small simulated malformed share of traffic for resilience testing

### `adapter-netconf`

- default host port: `7002`
- routes:
  - `GET /health`
  - `GET /metrics`
  - `POST /telemetry`
- flattens hierarchical payloads into section records
- publishes records to Redis stream `stream:raw.netconf`
- intentionally injects a small schema mismatch by renaming `forwardingLatencyMs` to `delay_ms`; the normalizer maps it back

### `normalizer`

- consumes `stream:raw.ves` and `stream:raw.netconf`
- maps both protocols into the canonical schema in `shared/models.py`
- writes canonical events to `stream:norm.telemetry`
- stores latest entity state in `entity:{entity_id}`
- mirrors canonical events to Kafka topic `telemetry-norm`

### `telemetry-exporter`

- consumes Kafka topic `telemetry-norm`
- writes telemetry points to InfluxDB measurement `telemetry`
- polls Redis hash `faults:active`
- writes fault summaries and active-fault details to InfluxDB measurement `faults`

## Data Contracts

Redis streams:

- `stream:raw.ves`
- `stream:raw.netconf`
- `stream:norm.telemetry`
- `stream:fault.events`

Redis hashes:

- `entity:{entity_id}`
- `faults:active`

Kafka topic:

- `telemetry-norm`

InfluxDB measurements:

- `telemetry`
- `faults`

## Canonical Event Model

`shared/models.py` defines the canonical event schema used by simulation, ingestion, AIOps, and API services. Core fields include:

- event, site, node, and entity identifiers
- domain and optional slice identifiers
- KPI payload
- derived fields such as `congestionScore`, `healthScore`, and `misroutingScore`
- scenario and severity metadata when faults are active

## Key Configuration

Shared variables from `shared/config.py` include:

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
docker compose up --build redis zookeeper kafka influxdb adapter-ves adapter-netconf normalizer telemetry-exporter
```

## Current Limits

- The adapters expose Prometheus-format `/metrics`, but the integrated Compose stack does not start Prometheus.
- `normalizer` and `telemetry-exporter` are worker services and do not expose HTTP APIs.
- Schema changes in `shared/` affect simulation, AIOps, and API services.
