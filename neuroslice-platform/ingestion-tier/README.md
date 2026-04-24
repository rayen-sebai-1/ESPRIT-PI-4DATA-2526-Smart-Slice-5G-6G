# Ingestion Tier

The ingestion tier receives simulator telemetry, normalizes heterogeneous payloads into the shared canonical event schema, and forwards the results to Redis, Kafka, and InfluxDB consumers.

## Implemented Components

This tier currently contains:

- `adapter-ves/`
- `adapter-netconf/`
- `normalizer/`
- `telemetry-exporter/`
- `shared/`

## Runtime Responsibilities

### `adapter-ves`

FastAPI service that accepts VES-style telemetry from the Core and RAN simulators.

- HTTP routes:
  - `GET /health`
  - `GET /metrics`
  - `POST /events`
- default Compose port: `7001`
- publishes accepted payloads to Redis stream `stream:raw.ves`
- simulates malformed payload rejection at roughly 5%

### `adapter-netconf`

FastAPI service that accepts hierarchical NETCONF-like payloads from the Edge simulator.

- HTTP routes:
  - `GET /health`
  - `GET /metrics`
  - `POST /telemetry`
- default Compose port: `7002`
- flattens nested NETCONF sections into flat records
- publishes records to Redis stream `stream:raw.netconf`
- simulates schema mismatch by renaming `forwardingLatencyMs` to `delay_ms` in a small share of requests

### `normalizer`

Async worker with no HTTP surface.

- consumes:
  - `stream:raw.ves`
  - `stream:raw.netconf`
- maps both protocols into the canonical schema defined in `shared/models.py`
- writes normalized events to Redis stream `stream:norm.telemetry`
- mirrors normalized events to Kafka topic `telemetry-norm`
- stores latest entity state in Redis hash `entity:{entityId}`
- handles the known NETCONF mismatch by remapping `delay_ms` back to `forwardingLatencyMs`

### `telemetry-exporter`

Async worker with no HTTP surface.

- consumes Kafka topic `telemetry-norm`
- writes canonical telemetry into InfluxDB measurement `telemetry`
- polls Redis hash `faults:active`
- writes fault summary/detail points into InfluxDB measurement `faults`

### `shared`

Shared Python package used across multiple tiers.

Current shared modules include:

- `config.py`
- `models.py`
- `redis_client.py`

These definitions are imported by simulation, ingestion, AIOps, and API services.

## Data Contracts

Primary Redis streams:

- `stream:raw.ves`
- `stream:raw.netconf`
- `stream:norm.telemetry`
- `stream:fault.events`

Primary Redis hashes and keys:

- `entity:{entityId}` for latest normalized entity state
- `faults:active` for active injected faults

Primary Kafka topic:

- `telemetry-norm`

Primary InfluxDB measurements:

- `telemetry`
- `faults`

## Canonical Model

The canonical event model is defined in `shared/models.py` and includes:

- domain: `core`, `edge`, `ran`
- entity identifiers and entity types
- optional slice metadata
- protocol source (`ves` or `netconf`)
- raw KPI fields
- derived metrics such as:
  - `congestionScore`
  - `healthScore`
  - `misroutingScore`
- scenario identifier and severity

## Key Environment Variables

Shared ingestion config comes from `shared/config.py` and includes:

- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_DB`
- `STREAM_MAXLEN`
- `TICK_INTERVAL_SEC`
- `SIM_SPEED`
- `SERVICE_NAME`
- `SITE_ID`
- `VES_ADAPTER_URL`
- `NETCONF_ADAPTER_URL`
- `NORMALIZER_URL`
- `FAULT_ENGINE_URL`
- `METRICS_PORT`

Additional component-specific variables:

- `normalizer`
  - `KAFKA_BROKER`
  - `KAFKA_TOPIC`
- `telemetry-exporter`
  - `KAFKA_BROKER`
  - `KAFKA_TOPIC`
  - `INFLUXDB_URL`
  - `INFLUXDB_TOKEN`
  - `INFLUXDB_ORG`
  - `INFLUXDB_BUCKET`

## Running The Tier

Run the ingestion services through the main Compose file:

```bash
cd neuroslice-platform/infrastructure
docker compose up --build adapter-ves adapter-netconf normalizer telemetry-exporter
```

Recommended dependencies:

- `redis`
- `kafka`
- `influxdb`

## Observability Note

The two adapters expose Prometheus-format `/metrics` endpoints, but the current top-level Compose stack does not include a Prometheus service.

## Folder Map

```text
ingestion-tier/
|-- README.md
|-- adapter-netconf/
|-- adapter-ves/
|-- normalizer/
|-- shared/
`-- telemetry-exporter/
```
