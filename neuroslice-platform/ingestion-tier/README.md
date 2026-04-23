# Ingestion Tier

Telemetry ingress and normalization layer for NeuroSlice. It receives simulator events, harmonizes them into a canonical schema, and forwards them to streaming and observability backends.

## Tier Purpose

This tier is the data backbone between simulation and intelligence.

Responsibilities:

- Accept raw VES and NETCONF-like telemetry.
- Simulate realistic ingestion noise (malformed payloads, schema mismatch).
- Normalize heterogeneous payloads into a shared canonical event model.
- Persist latest per-entity state for low-latency reads.
- Fan out normalized events to Kafka and Influx pipelines.

## Components

- `adapter-ves`
- FastAPI service for `POST /events`
- Exposes `/health` and Prometheus `/metrics`
- Publishes accepted payloads to `stream:raw.ves`

- `adapter-netconf`
- FastAPI service for `POST /telemetry`
- Exposes `/health` and Prometheus `/metrics`
- Flattens NETCONF blobs and injects controlled schema mismatch (`delay_ms`)
- Publishes records to `stream:raw.netconf`

- `normalizer`
- Async background worker (no HTTP port)
- Consumes `stream:raw.ves` and `stream:raw.netconf`
- Produces canonical events to `stream:norm.telemetry`
- Mirrors events to Kafka topic `telemetry-norm`
- Stores latest entity state in Redis hash `entity:{entityId}`

- `telemetry-exporter`
- Async worker that consumes Kafka `telemetry-norm`
- Writes telemetry points to Influx measurement `telemetry`
- Polls `faults:active` and writes measurement `faults`

- `shared`
- Shared config, enums/schemas, and Redis helpers used by ingestion, simulation, API, and AIOps tiers

## Stream and Data Contracts

Raw ingress streams:

- `stream:raw.ves`
- `stream:raw.netconf`

Normalized stream:

- `stream:norm.telemetry`

Redis state:

- `entity:{entityId}` (latest canonical per-entity snapshot)

Kafka egress:

- `telemetry-norm`

## Running the Tier

Preferred (with dependencies):

```bash
cd neuroslice-platform/infrastructure
docker compose up --build adapter-ves adapter-netconf normalizer telemetry-exporter
```

Recommended dependency set:

- `redis`
- `kafka`
- `influxdb`

## Troubleshooting Checklist

- If normalized events are missing:
- verify adapters are receiving payloads (`/metrics`).
- verify normalizer consumer group can read raw streams.
- verify Redis connectivity and stream names in env vars.

- If Grafana telemetry is empty:
- verify Kafka topic `telemetry-norm` has new messages.
- verify exporter can write to Influx (`INFLUXDB_*` envs).

## Folder Map

```text
ingestion-tier/
├── adapter-ves/
├── adapter-netconf/
├── normalizer/
├── telemetry-exporter/
└── shared/
```
