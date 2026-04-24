# Infrastructure Layer

The infrastructure layer is the canonical local integration entry point for NeuroSlice. It keeps the default runtime lightweight and adds the Scenario B MLOps control plane only when the `mlops` profile is enabled.

## Runtime Modes

Normal runtime:

```bash
cd neuroslice-platform/infrastructure
cp .env.example .env
docker compose up --build
```

Runtime plus Scenario B MLOps:

```bash
cd neuroslice-platform/infrastructure
cp .env.example .env
docker compose --profile mlops up --build
```

Validate the rendered Compose file:

```bash
cd neuroslice-platform/infrastructure
docker compose config
```

## What Starts By Default

`docker compose up --build` starts the shared platform, simulation tier, ingestion tier, AIOps workers, dashboard tier, and Grafana.

It does not start:

- `mlops-postgres`
- `minio`
- `minio-init`
- `mlflow-server`
- `elasticsearch`
- `logstash`
- `mlops-api`
- `mlops-worker`

Those services are optional so the normal runtime stays lighter and does not publish extra MLOps ports unless requested.

## Scenario B Profile

`docker compose --profile mlops up --build` adds the integrated MLOps runtime services:

- `mlops-postgres` for MLflow metadata
- `minio` for artifact storage
- `minio-init` to create the default artifact bucket
- `mlflow-server` for tracking and artifact serving
- `elasticsearch` and `logstash` for internal MLOps log ingestion
- `mlops-api` built from `../mlops-tier/batch-orchestrator`

`mlops-worker` is intentionally not part of the `mlops` profile. Run it only when you want the offline pipeline to execute manually.

## URLs

Default runtime URLs:

- API BFF: `http://localhost:8000`
- VES adapter: `http://localhost:7001`
- NETCONF adapter: `http://localhost:7002`
- fault-engine: `http://localhost:7004`
- InfluxDB: `http://localhost:8086`
- Grafana: `http://localhost:3000`
- Kong gateway: `http://localhost:8008`
- React dashboard: `http://localhost:5173`

Scenario B MLOps URLs:

- MLflow UI: `http://localhost:5000`
- MinIO API: `http://localhost:9000`
- MinIO console: `http://localhost:9001`
- MLOps API: `http://localhost:8010`

The dashboard stack is preconfigured for future ML engineer features through:

- `MLOPS_API_BASE_URL=http://mlops-api:8010`
- `MLFLOW_TRACKING_URI=http://mlflow-server:5000`

These environment variables are set on `dashboard-backend`, but no UI integration is implemented yet.

## AIOps Artifact Access

The AIOps services do not require the `mlops` profile to start. They keep reading local promoted artifacts from `../mlops-tier/batch-orchestrator` through read-only mounts:

- `models/`
- `data/`
- `mlruns/`
- `mlflow.db`
- `src/`

`models/registry.json` remains the first discovery target when it exists. This preserves the current fallback mode while keeping the future hot-reload path available.

## Manual Offline Pipeline

Local, outside Docker:

```bash
cd neuroslice-platform/mlops-tier/batch-orchestrator
pip install -r requirements.txt
make pipeline
```

Docker, against the integrated Scenario B services:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops --profile mlops-worker run --rm mlops-worker
```

## Artifact Flow

The integrated Scenario B flow is:

1. training
2. ONNX FP16 export
3. MLflow metadata in `mlops-postgres`
4. artifacts in MinIO under `MLFLOW_ARTIFACT_BUCKET`
5. promoted registry metadata in `../mlops-tier/batch-orchestrator/models/registry.json`
6. AIOps runtime reload scaffolding consuming those promoted artifacts later

## Key Environment Variables

The main template is `.env.example`.

Core runtime variables:

- `SITE_ID`
- `TICK_INTERVAL_SEC`
- `SIM_SPEED`
- `REDIS_PORT`
- `STREAM_MAXLEN`
- `API_PORT`
- `VES_PORT`
- `NETCONF_PORT`
- `FAULT_ENGINE_PORT`
- `GRAFANA_PORT`
- `DASHBOARD_POSTGRES_PORT`
- `DASHBOARD_FRONTEND_PORT`
- `DASHBOARD_KONG_PORT`

Scenario B profile variables:

- `MLOPS_POSTGRES_DB`
- `MLOPS_POSTGRES_USER`
- `MLOPS_POSTGRES_PASSWORD`
- `MLOPS_POSTGRES_PORT`
- `MINIO_ROOT_USER`
- `MINIO_ROOT_PASSWORD`
- `MINIO_API_PORT`
- `MINIO_CONSOLE_PORT`
- `MLFLOW_ARTIFACT_BUCKET`
- `MLFLOW_TRACKING_PORT`
- `MLOPS_API_PORT`
- `MLFLOW_TRACKING_URI`
- `MLFLOW_BACKEND_STORE_URI`
- `MLFLOW_ARTIFACT_ROOT`
- `MLFLOW_S3_ENDPOINT_URL`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `MLOPS_LOG_MONITORING_MODE`

Dashboard and auth variables:

- `DASHBOARD_POSTGRES_DB`
- `DASHBOARD_POSTGRES_SUPERUSER`
- `DASHBOARD_POSTGRES_SUPERPASS`
- `AUTH_DB_USER`
- `AUTH_DB_PASSWORD`
- `DASHBOARD_DB_USER`
- `DASHBOARD_DB_PASSWORD`
- `DASHBOARD_JWT_SECRET`
- `JWT_ACCESS_TOKEN_EXPIRES_MINUTES`
- `JWT_REFRESH_TOKEN_EXPIRES_DAYS`
- `ARGON2_MEMORY_COST`
- `ARGON2_TIME_COST`
- `ARGON2_PARALLELISM`
- `REFRESH_COOKIE_NAME`
- `REFRESH_COOKIE_PATH`
- `REFRESH_COOKIE_SECURE`
- `REFRESH_COOKIE_SAMESITE`
- `DASHBOARD_DATA_PROVIDER`

## Folder Map

```text
infrastructure/
|-- .env
|-- .env.example
|-- README.md
|-- docker-compose.yml
|-- observability/
`-- postgres-init/
```
