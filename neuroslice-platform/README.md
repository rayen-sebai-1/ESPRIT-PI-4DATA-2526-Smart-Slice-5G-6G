# NeuroSlice Platform

NeuroSlice is the platform subtree of this repository. It contains the integrated local runtime, all service tiers, and the offline MLOps project used by the runtime AIOps workers.

## Platform Snapshot

Implemented tiers in the current workspace:

- `simulation-tier`: SimPy-based Core, Edge, and RAN simulators plus the fault engine
- `ingestion-tier`: VES and NETCONF adapters, the normalizer, the telemetry exporter, and shared models/config
- `aiops-tier`: runtime workers for congestion detection, SLA assurance, and slice classification
- `api-dashboard-tier`: public BFF, auth service, dashboard backend, Kong gateway, and React frontend
- `infrastructure`: the integrated Compose runtime plus Redis, Kafka, PostgreSQL, InfluxDB, and Grafana wiring
- `mlops-tier/batch-orchestrator`: preprocessing, training, lifecycle metadata, prediction API, tests, notebooks, and reports

Placeholder-only tiers:

- `control-tier`
- `agentic-ai-tier`

Deferred runtime service:

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

Optional `mlops-worker` runs the offline training pipeline on demand.

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
curl http://localhost:7001/health
curl http://localhost:7002/health
curl http://localhost:7004/health
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

## Current Workspace Notes

- `control-tier` and `agentic-ai-tier` still contain documentation only.
- `agentic-ai-tier` has commented Compose stubs and `.env.example` variables reserved for future agent services, but nothing is active.
- Runtime AIOps workers always mount `mlops-tier/batch-orchestrator/models`, `data`, `mlruns`, `mlflow.db`, and `src` read-only.
- The tracked `mlops-tier/batch-orchestrator/models/registry.json` now contains generated metadata, but there are still no promoted model entries for runtime auto-discovery.
- Most generated MLOps artifacts, including `data/processed/`, `models/*.pt`, `models/*.pth`, `mlruns/`, and local MLflow state, are gitignored and may be absent in a fresh clone.
- Adapters expose Prometheus-format `/metrics`, but the integrated runtime does not currently start a Prometheus service.

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
`-- simulation-tier/
```
