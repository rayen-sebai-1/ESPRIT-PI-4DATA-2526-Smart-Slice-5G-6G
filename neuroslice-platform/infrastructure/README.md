# Infrastructure Layer

The infrastructure layer is the canonical local entry point for the NeuroSlice platform. It wires together the simulators, ingestion pipeline, runtime AIOps services, dashboard stack, observability tooling, and the optional integrated MLOps control plane.

## Runtime Modes

Default platform runtime:

```bash
cd neuroslice-platform/infrastructure
cp .env.example .env
docker compose up --build
```

Platform runtime plus integrated MLOps services:

```bash
cd neuroslice-platform/infrastructure
cp .env.example .env
docker compose --profile mlops up --build
```

Run the offline MLOps worker against the integrated services:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops --profile mlops-worker run --rm mlops-worker
```

Useful validation:

```bash
cd neuroslice-platform/infrastructure
docker compose config
```

## What Starts by Default

`docker compose up --build` starts:

- Redis
- Zookeeper
- Kafka
- InfluxDB
- PostgreSQL
- Grafana
- simulation services
- ingestion services
- runtime AIOps workers
- `api-bff-service`
- `auth-service`
- `dashboard-backend`
- `kong-gateway`
- `react-dashboard`

It does not start the integrated MLOps services unless the `mlops` profile is enabled.

## Published URLs

Default runtime:

- Public API/BFF: `http://localhost:8000`
- VES adapter: `http://localhost:7001`
- NETCONF adapter: `http://localhost:7002`
- Fault engine: `http://localhost:7004`
- React dashboard: `http://localhost:5173`
- Kong gateway: `http://localhost:8008`
- Grafana: `http://localhost:3000`
- InfluxDB: `http://localhost:8086`
- Redis: `localhost:6379`
- Platform PostgreSQL: `localhost:5432`
- Kafka host listener: `localhost:29092`

Optional `mlops` profile:

- MLflow UI: `http://localhost:5000`
- MinIO API: `http://localhost:9000`
- MinIO console: `http://localhost:9001`
- MLOps API: `http://localhost:8010`
- MLOps PostgreSQL: `localhost:5433`

## MLOps Data Ownership

The integrated MLOps profile keeps platform and MLOps storage separate:

- `postgres` is used only by `auth-service` and `dashboard-backend`
- `mlops-postgres` is used only by the MLflow backend store
- MinIO bucket `mlflow-artifacts` stores MLflow artifacts, model binaries, ONNX, ONNX FP16, preprocessors, scalers, encoders, and reports

The MLflow server is configured with:

- backend store URI: `postgresql+psycopg2://...@mlops-postgres:5432/mlflow`
- default artifact root: `s3://mlflow-artifacts`
- S3 endpoint: `http://minio:9000`
- AWS credentials from `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`

## Environment Variables

Primary template:

- `.env.example`

Key values already wired into Compose:

- simulation settings: `SITE_ID`, `TICK_INTERVAL_SEC`, `SIM_SPEED`
- runtime thresholds: `CONGESTION_THRESHOLD`, `SLICE_MISMATCH_CONFIDENCE_THRESHOLD`, `SLA_RISK_THRESHOLD`, `MODEL_POLL_INTERVAL_SEC`
- public ports: `REDIS_PORT`, `API_PORT`, `VES_PORT`, `NETCONF_PORT`, `FAULT_ENGINE_PORT`, `GRAFANA_PORT`, `DASHBOARD_FRONTEND_PORT`, `DASHBOARD_KONG_PORT`
- optional MLOps ports and credentials: `MLOPS_POSTGRES_*`, `MINIO_*`, `MLFLOW_*`, `AWS_*`, `MLOPS_API_PORT`, `MLOPS_LOG_MONITORING_MODE`
- dashboard backend config: `DASHBOARD_JWT_SECRET`, `DASHBOARD_DATA_PROVIDER`

## Current Caveats

- platform PostgreSQL is still bound to fixed host port `5432`; `DASHBOARD_POSTGRES_PORT` in `.env.example` is not wired yet
- `auth-service` and the platform `postgres` service still include development credentials directly in the Compose file
- `dashboard-backend` already reads `DASHBOARD_JWT_SECRET` from `.env`
- `.env.example` still contains reserved variables for future agentic services, but the related Compose services are commented out
- runtime AIOps services always mount `../mlops-tier/batch-orchestrator` paths; if generated artifacts are missing locally, the workers fall back to local heuristics

If you need production-style secret management, update the Compose file in addition to `.env`.

## AIOps Artifact Access

The runtime AIOps services mount registry and generated local artifacts from `../mlops-tier/batch-orchestrator`, even when the `mlops` profile is disabled:

- `models/`
- `data/`
- `src/`

They read `models/registry.json` and prefer promoted production artifacts in this order: ONNX FP16, ONNX, local model fallback, then heuristic fallback.

## MLOps Verification

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops up --build
docker compose --profile mlops --profile mlops-worker run --rm mlops-worker
```

Verify:

- MLflow UI: `http://localhost:5000`
- MinIO console: `http://localhost:9001`
- MLOps API: `http://localhost:8010`
- `../mlops-tier/batch-orchestrator/models/registry.json` contains a `promoted=true`, `stage=production` entry

## Common Operations

Stop the stack:

```bash
cd neuroslice-platform/infrastructure
docker compose down
```

Remove containers and persisted volumes:

```bash
cd neuroslice-platform/infrastructure
docker compose down -v
```

## Current Limits

- The default stack uses local-development credentials and should not be treated as production-ready.
- `mlops-worker` is intentionally manual and does not start during `docker compose --profile mlops up --build`.
- Prometheus-format adapter metrics are available, but the Compose stack does not currently include a Prometheus service.
