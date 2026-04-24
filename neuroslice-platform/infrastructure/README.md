# Infrastructure Layer

The infrastructure layer is the authoritative local integration environment for NeuroSlice. It wires the active tiers together through Docker Compose and carries the shared data stores, observability assets, and dashboard database bootstrap logic.

## What Exists In This Folder

Committed files and folders:

- `docker-compose.yml`
- `.env.example`
- `.env`
- `postgres-init/`
- `observability/`

Current observability assets:

- `observability/grafana/provisioning/datasources/influxdb.yml`
- `observability/grafana/provisioning/dashboards/dashboards.yml`
- `observability/grafana/provisioning/dashboards/neuroslice_overview.json`
- `observability/query.flux`
- `observability/metrics.txt`

Current PostgreSQL bootstrap asset:

- `postgres-init/001-create-dashboard-roles.sh`

There are no committed `k8s/` or `istio/` directories in the current workspace.

## Compose Service Topology

### Core infrastructure services

- `redis`
- `zookeeper`
- `kafka`
- `influxdb`
- `postgres`
- `mlflow-postgres`
- `minio`
- `minio-init`
- `mlflow`
- `mlops-api`
- `elasticsearch`
- `logstash`
- `kibana`
- `grafana`

### Simulation tier services

- `fault-engine`
- `simulator-core`
- `simulator-edge`
- `simulator-ran`

### Ingestion tier services

- `adapter-ves`
- `adapter-netconf`
- `normalizer`
- `telemetry-exporter`

### AIOps tier services

- `congestion-detector`
- `slice-classifier`
- `sla-assurance`

### API/dashboard tier services

- `api-bff-service`
- `auth-service`
- `dashboard-backend`
- `kong-gateway`
- `react-dashboard`

## Quick Start

```bash
cd neuroslice-platform/infrastructure
cp .env.example .env
docker compose up --build
```

If you previously started `mlops-tier/batch-orchestrator/docker-compose.yml`, stop it before using the integrated infrastructure stack unless you intentionally override the overlapping host ports.

## Default Ports And URLs

- API BFF: `http://localhost:8000`
- API BFF docs: `http://localhost:8000/docs`
- VES adapter: `http://localhost:7001`
- NETCONF adapter: `http://localhost:7002`
- fault-engine: `http://localhost:7004`
- Redis: `localhost:6379`
- Kafka host listener: `localhost:29092`
- InfluxDB: `http://localhost:8086`
- PostgreSQL: `localhost:5432`
- MLflow PostgreSQL: `localhost:5433`
- MLflow: `http://localhost:5000`
- MLOps API: `http://localhost:8010`
- MinIO API: `http://localhost:9000`
- MinIO console: `http://localhost:9001`
- Elasticsearch: `http://localhost:9200`
- Logstash HTTP input: `http://localhost:8081/predictions`
- Kibana: `http://localhost:5601`
- Grafana: `http://localhost:3000`
- Kong gateway: `http://localhost:8008`
- React dashboard: `http://localhost:5173`

Protected dashboard routes exposed through Kong:

- `/api/auth/*`
- `/api/dashboard/*`

## Environment Variables

The main template is `.env.example`.

Variables actively used by the current Compose stack include:

- site and simulation:
  - `SITE_ID`
  - `TICK_INTERVAL_SEC`
  - `SIM_SPEED`
- shared platform:
  - `REDIS_PORT`
  - `STREAM_MAXLEN`
  - `API_PORT`
  - `MLOPS_API_PORT`
  - `VES_PORT`
  - `NETCONF_PORT`
  - `FAULT_ENGINE_PORT`
  - `GRAFANA_PORT`
  - `MLFLOW_PORT`
  - `MLFLOW_POSTGRES_PORT`
  - `MINIO_API_PORT`
  - `MINIO_CONSOLE_PORT`
  - `LOGSTASH_PORT`
  - `ELASTICSEARCH_PORT`
  - `KIBANA_PORT`
- AIOps thresholds:
  - `CONGESTION_THRESHOLD`
  - `SLICE_MISMATCH_CONFIDENCE_THRESHOLD`
  - `SLA_RISK_THRESHOLD`
  - `MODEL_POLL_INTERVAL_SEC`
- MLOps Scenario B:
  - `MLFLOW_TRACKING_URI`
  - `MLFLOW_BACKEND_STORE_URI`
  - `MLFLOW_ARTIFACT_ROOT`
  - `MLFLOW_POSTGRES_USER`
  - `MLFLOW_POSTGRES_PASSWORD`
  - `MLFLOW_POSTGRES_DB`
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
  - `MLFLOW_S3_ENDPOINT_URL`
  - `MINIO_ROOT_USER`
  - `MINIO_ROOT_PASSWORD`
  - `MINIO_BUCKET`
  - `MLOPS_LOG_MONITORING_MODE`
- dashboard database and auth:
  - `DASHBOARD_POSTGRES_PORT`
  - `DASHBOARD_POSTGRES_DB`
  - `DASHBOARD_POSTGRES_SUPERUSER`
  - `DASHBOARD_POSTGRES_SUPERPASS`
  - `AUTH_DB_USER`
  - `AUTH_DB_PASSWORD`
  - `DASHBOARD_DB_USER`
  - `DASHBOARD_DB_PASSWORD`
  - `DASHBOARD_FRONTEND_PORT`
  - `DASHBOARD_KONG_PORT`
  - `DASHBOARD_JWT_SECRET`
  - `JWT_ACCESS_TOKEN_EXPIRES_MINUTES`
  - `JWT_REFRESH_TOKEN_EXPIRES_DAYS`
  - `ARGON2_MEMORY_COST`
  - `ARGON2_TIME_COST`
  - `ARGON2_PARALLELISM`
  - `REFRESH_COOKIE_NAME`
  - `REFRESH_COOKIE_SECURE`
  - `REFRESH_COOKIE_SAMESITE`
  - `DASHBOARD_DATA_PROVIDER`
- Grafana:
  - `GRAFANA_USER`
  - `GRAFANA_PASSWORD`

Template variables currently present but not wired to an active service or port mapping in `docker-compose.yml`:

- `EXPORTER_PORT`
- `PROMETHEUS_PORT`

The current Compose stack does not define a Prometheus service.

## Database Bootstrap

`postgres-init/001-create-dashboard-roles.sh` runs when PostgreSQL initializes and:

- creates the auth and dashboard database roles if needed
- grants database connectivity
- creates schemas:
  - `auth`
  - `dashboard`
- grants `dashboard-backend` read access to the auth schema objects it needs

## Dashboard Notes

- `auth-service` and `dashboard-backend` are internal-only Compose services
- `kong-gateway` is the public browser-facing entry point for protected dashboard APIs
- `react-dashboard` proxies `/api/*` to Kong
- `api-bff-service` remains a separate public API surface on port `8000`

## Useful Compose Subsets

Run only the API/dashboard stack plus database:

```bash
cd neuroslice-platform/infrastructure
docker compose up --build postgres api-bff-service auth-service dashboard-backend kong-gateway react-dashboard
```

Run only the simulation, ingestion, and AIOps runtime path:

```bash
cd neuroslice-platform/infrastructure
docker compose up --build redis zookeeper kafka influxdb adapter-ves adapter-netconf normalizer congestion-detector slice-classifier sla-assurance fault-engine simulator-core simulator-edge simulator-ran telemetry-exporter api-bff-service grafana
```

Run the integrated MLOps Scenario B stack:

```bash
cd neuroslice-platform/infrastructure
docker compose up --build mlflow-postgres minio minio-init mlflow mlops-api elasticsearch logstash kibana
```

## Folder Map

```text
infrastructure/
|-- .env
|-- .env.example
|-- README.md
|-- docker-compose.yml
|-- observability/
|   |-- grafana/
|   |-- metrics.txt
|   `-- query.flux
`-- postgres-init/
    `-- 001-create-dashboard-roles.sh
```
