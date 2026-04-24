# NeuroSlice Platform

NeuroSlice is an end-to-end 5G/6G network-slicing platform organized around a Docker Compose runtime for live simulation and a separate MLOps project for training and prediction workflows.

## Platform Snapshot

Implemented tiers in the current workspace:

- `simulation-tier`: SimPy-based Core, Edge, and RAN simulators plus the fault engine
- `ingestion-tier`: VES and NETCONF adapters, normalization pipeline, telemetry exporter, and shared models/config
- `aiops-tier`: runtime workers for congestion detection, SLA assurance, and slice classification
- `api-dashboard-tier`: public API/BFF, auth service, dashboard backend, Kong gateway, and React frontend
- `infrastructure`: Compose entry point, Redis, Kafka, PostgreSQL, InfluxDB, Grafana, and optional integrated MLOps services
- `mlops-tier/batch-orchestrator`: preprocessing, training, evaluation, registry metadata, and prediction API

Placeholder-only tiers:

- `control-tier`
- `agentic-ai-tier`

Deferred service:

- `aiops-tier/misrouting-detector`

## Runtime Topology

Default `docker compose up --build` in `infrastructure/` starts:

- Redis
- Zookeeper
- Kafka
- InfluxDB
- PostgreSQL
- Grafana
- `adapter-ves`
- `adapter-netconf`
- `normalizer`
- `telemetry-exporter`
- `simulator-core`
- `simulator-edge`
- `simulator-ran`
- `fault-engine`
- `congestion-detector`
- `slice-classifier`
- `sla-assurance`
- `api-bff-service`
- `auth-service`
- `dashboard-backend`
- `kong-gateway`
- `react-dashboard`

Optional `mlops` profile adds:

- `mlops-postgres`
- `minio`
- `minio-init`
- `mlflow-server`
- `elasticsearch`
- `logstash`
- `mlops-api`

Optional `mlops-worker` profile runs the offline pipeline worker on demand.

## End-to-End Data Flow

```text
simulator-core / simulator-ran -> adapter-ves -> stream:raw.ves
simulator-edge                 -> adapter-netconf -> stream:raw.netconf

stream:raw.ves + stream:raw.netconf
  -> normalizer
  -> stream:norm.telemetry
  -> entity:{entity_id}
  -> Kafka topic telemetry-norm

stream:norm.telemetry
  -> congestion-detector -> events.anomaly -> aiops:congestion:{entity_id}
  -> slice-classifier    -> events.slice.classification -> aiops:slice_classification:{entity_id}
  -> sla-assurance       -> events.sla -> aiops:sla:{entity_id}

telemetry-norm -> telemetry-exporter -> InfluxDB

api-bff-service
  -> Redis state and streams
  -> fault-engine proxy

react-dashboard -> kong-gateway -> auth-service / dashboard-backend
```

## Quick Start

```bash
cd neuroslice-platform/infrastructure
cp .env.example .env
docker compose up --build
```

Useful checks:

```bash
curl http://localhost:8000/health
curl http://localhost:7004/health
curl http://localhost:7001/health
curl http://localhost:7002/health
curl "http://localhost:8000/api/v1/aiops/congestion/latest?limit=20"
```

Optional integrated MLOps services:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops up --build
```

Manual offline pipeline against the integrated stack:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops --profile mlops-worker run --rm mlops-worker
```

## Important URLs

- Public API/BFF: `http://localhost:8000`
- VES adapter: `http://localhost:7001`
- NETCONF adapter: `http://localhost:7002`
- Fault engine: `http://localhost:7004`
- React dashboard: `http://localhost:5173`
- Kong gateway: `http://localhost:8008`
- Grafana: `http://localhost:3000`
- InfluxDB: `http://localhost:8086`
- MLflow UI: `http://localhost:5000` (`mlops` profile)
- MinIO console: `http://localhost:9001` (`mlops` profile)
- MLOps API: `http://localhost:8010` (`mlops` profile)

## Tier Notes

### Simulation

- Three stateful simulators model Core, Edge, and RAN behavior.
- The fault engine exposes scenario and manual fault injection endpoints.
- Scenario files are mounted into services at `/scenarios`.

### Ingestion

- `adapter-ves` accepts `POST /events`.
- `adapter-netconf` accepts `POST /telemetry`.
- `normalizer` emits canonical events to `stream:norm.telemetry` and Kafka topic `telemetry-norm`.
- `telemetry-exporter` writes telemetry and fault snapshots to InfluxDB.

### Runtime AIOps

- All runtime workers consume `stream:norm.telemetry`.
- Runtime outputs are written to Redis, Kafka, and InfluxDB.
- Model discovery first checks `mlops-tier/batch-orchestrator/models/registry.json`.
- The current committed `registry.json` is empty, so fallback loading remains important.

### API and Dashboard

- `api-bff-service` is the public telemetry and control API.
- `auth-service` and `dashboard-backend` are internal services exposed to browsers through Kong.
- `dashboard-backend` defaults to `temporary_mock` provider mode in Compose.
- The React dashboard uses Kong for all browser API requests.

### MLOps

- `batch-orchestrator` contains the training scripts, prediction API, notebooks, tests, and lifecycle utilities.
- Runtime AIOps services mount `models/`, `data/`, `mlruns/`, and `mlflow.db` from that project.
- Standalone and integrated MLOps modes share the same local artifacts.

## Environment and Configuration Notes

The main environment template is `infrastructure/.env.example`.

What is configurable through `.env` today:

- simulation speed and site identity
- host ports for Redis, public APIs, Grafana, and optional MLOps services
- runtime AIOps thresholds
- optional MLOps profile storage and MLflow settings
- dashboard backend JWT secret and provider selection

Current Compose caveats:

- platform PostgreSQL is still published on fixed host port `5432`
- `auth-service` and the platform `postgres` service still use development defaults embedded directly in `infrastructure/docker-compose.yml`
- `dashboard-backend` already reads `DASHBOARD_JWT_SECRET` from `.env`

For non-local environments, update both `.env` and the compose file where values are still hardcoded.

## Known Gaps

- `control-tier` and `agentic-ai-tier` are placeholders only.
- `misrouting-detector` is intentionally deferred.
- The `bff` dashboard provider currently supports national overview aggregation and the models catalog, but not full regional, session, or prediction workflows.
- Adapters expose Prometheus-format `/metrics`, but the runtime stack does not currently start a Prometheus container.

## Repository Map

```text
neuroslice-platform/
|-- agentic-ai-tier/
|-- aiops-tier/
|-- api-dashboard-tier/
|-- control-tier/
|-- infrastructure/
|-- ingestion-tier/
|-- mlops-tier/
|   `-- batch-orchestrator/
|-- reports/
|-- simulation-tier/
`-- src/
```
