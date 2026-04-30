# Infrastructure Layer

Last verified: 2026-04-30.

The infrastructure layer is the canonical local entry point for NeuroSlice. It wires simulators, ingestion, runtime AIOps, control-tier services, dashboard services, agentic services, observability, and the optional integrated MLOps stack.

## Runtime Modes

Default platform runtime (includes mlops-runner and drift-monitor):

```bash
cd neuroslice-platform/infrastructure
docker compose up --build
```

Platform runtime plus integrated MLOps services:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops up --build
```

Platform runtime plus Scenario B statistical drift detection (alibi-detect):

```bash
cd neuroslice-platform/infrastructure
docker compose --profile drift up --build
```

Platform runtime plus MLOps and statistical drift detection:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops --profile drift up --build
```

Run the offline MLOps worker against integrated services:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops --profile mlops-worker run --rm mlops-worker
```

Validate Compose configuration:

```bash
cd neuroslice-platform/infrastructure
docker compose config
```

## Scenario B Drift Detection

There are two drift detection services in the platform:

**mlops-tier drift-monitor** (default runtime, always-on):

A lightweight FastAPI service that counts anomaly events in the `events.anomaly` Redis stream over a sliding window. When the count exceeds the threshold it calls `mlops-runner` to trigger the full pipeline automatically. Relevant environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DRIFT_ANOMALY_THRESHOLD` | `5` | Anomaly events in window before triggering |
| `DRIFT_WINDOW_SECONDS` | `120` | Sliding window length in seconds |
| `DRIFT_COOLDOWN_SECONDS` | `600` | Minimum seconds between consecutive triggers |
| `DRIFT_POLL_INTERVAL_SECONDS` | `30` | Polling interval |
| `MLOPS_PIPELINE_ENABLED` | `true` | Set `false` to disable auto-trigger |

**aiops-tier drift-monitor** (`drift` profile, optional):

A statistically rigorous service using `alibi-detect[torch]` (PyTorch MMD test) that requires pre-built drift reference artifacts. It is a separate profile because PyTorch adds significant build time and image size.

| Variable | Default | Description |
|----------|---------|-------------|
| `DRIFT_AUTO_TRIGGER_MLOPS` | `false` | Set `true` to attempt MLOps pipeline trigger on drift |
| `DRIFT_REQUIRE_REFERENCES` | `false` | Set `true` to fail hard if reference artifacts are missing |
| `DRIFT_WINDOW_SIZE` | `500` | Rolling window sample count |
| `DRIFT_P_VALUE_THRESHOLD` | `0.01` | MMD p-value threshold |
| `DRIFT_TEST_INTERVAL_SEC` | `60` | Seconds between drift tests |
| `DRIFT_EMIT_COOLDOWN_SEC` | `300` | Seconds between repeated drift alerts per model |
| `DRIFT_MONITOR_PORT` | `7012` | Host port for aiops-tier drift-monitor |

See `SCENARIO_B_DRIFT_DETECTION.md` for the full architecture and verification guide.

## PostgreSQL Initialization Notes

Fresh local setup:

```bash
cd neuroslice-platform/infrastructure
docker compose up -d --build
```

If your local PostgreSQL volume was initialized with old or mismatched roles/users:

```bash
cd neuroslice-platform/infrastructure
docker compose down -v
docker compose up -d --build
```

Important behavior:

- PostgreSQL init scripts in `infrastructure/postgres-init` run only on first volume initialization.
- If `postgres_data` already exists, updating init scripts or DB credentials does not retroactively recreate roles/databases.
- For dashboard/auth DB recovery after credential mismatches, recreate volumes with `docker compose down -v`.

## Default Services

`docker compose up --build` starts:

- Redis
- Zookeeper
- Kafka
- InfluxDB
- PostgreSQL
- Grafana
- Prometheus (scrapes adapter-ves and adapter-netconf metrics on `:9090`)
- simulation services
- ingestion services
- runtime AIOps workers
- `api-bff-service`
- `auth-service`
- `dashboard-backend`
- `kong-gateway`
- `react-dashboard`
- `alert-management`
- `policy-control`
- `root-cause`
- `copilot-agent`
- `mlops-runner` (internal-only; no published port)
- `drift-monitor` (mlops-tier; internal-only at port 8030)

The integrated MLOps services start only with the `mlops` profile.

## Optional MLOps Services

The `mlops` profile starts:

- `mlops-postgres`
- `minio`
- `minio-init`
- `mlflow-server`
- `elasticsearch`
- `logstash`
- `kibana`
- `mlops-api`
- `mlops-runner` (internal-only worker that triggers the pipeline on behalf of `dashboard-backend` and `drift-monitor`)

The `mlops-worker` profile runs the offline training/promotion pipeline manually.

`mlops-runner` is the only service that owns the Docker socket. It accepts `POST /run-action` calls with a fixed action map (e.g. `full_pipeline`) and executes the corresponding make target inside the mlops-api container. Toggling `MLOPS_PIPELINE_ENABLED=false` immediately disables pipeline execution. See `mlops-tier/mlops-runner/README.md`.

## Published URLs

Default runtime:

- Public API/BFF: `http://localhost:8000`
- VES adapter: `http://localhost:7001`
- NETCONF adapter: `http://localhost:7002`
- Fault engine: `http://localhost:7004`
- Root-cause agent: `http://localhost:7005`
- Copilot agent: `http://localhost:7006`
- Drift monitor API/metrics: `http://localhost:7012` with `drift` profile
- React dashboard: `http://localhost:5173`
- Kong gateway: `http://localhost:8008`
- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- InfluxDB: `http://localhost:8086`
- Redis: `localhost:6379`
- Platform PostgreSQL: `localhost:5432`
- Kafka host listener: `localhost:29092`

Control-tier (standalone start — see `control-tier/README.md`):

- Alert management: `http://localhost:7010`
- Policy control: `http://localhost:7011`

Optional `mlops` profile:

- MLflow UI: `http://localhost:5000`
- MinIO API: `http://localhost:9000`
- MinIO console: `http://localhost:9001`
- MLOps API: `http://localhost:8010`
- MLOps PostgreSQL: `localhost:5433`
- Elasticsearch: `http://localhost:9200`
- Kibana: `http://localhost:5601`

The integrated Logstash HTTP input is internal to Docker Compose at `http://logstash:8081/predictions`.

## MLOps Data Ownership

Storage is split deliberately:

- `postgres`: auth and dashboard application data
- `mlops-postgres`: MLflow backend metadata
- MinIO bucket `mlflow-artifacts`: MLflow artifacts, model binaries, ONNX, ONNX FP16, preprocessing artifacts, reports
- local mounted `batch-orchestrator/models`: promoted-current artifacts consumed by AIOps services

MLflow server configuration:

- backend store URI: PostgreSQL on `mlops-postgres`
- default artifact root: `s3://mlflow-artifacts`
- S3 endpoint: `http://minio:9000`

## AIOps Artifact Access

Runtime AIOps services mount generated MLOps files read-only:

- `../mlops-tier/batch-orchestrator/models:/mlops/models:ro`
- `../mlops-tier/batch-orchestrator/data:/mlops/data:ro`
- `../mlops-tier/batch-orchestrator/src:/mlops/src:ro`

Primary production model paths:

- `/mlops/models/promoted/congestion_5g/current/model_fp16.onnx`
- `/mlops/models/promoted/sla_5g/current/model_fp16.onnx`
- `/mlops/models/promoted/slice_type_5g/current/model_fp16.onnx`

Services poll `metadata.json` with `MODEL_POLL_INTERVAL_SEC` and hot reload ONNX Runtime sessions without container restarts.

## Agentic Services

`root-cause` and `copilot-agent` are part of the default Compose runtime. They use Ollama through:

- `OLLAMA_BASE_URL`, default `http://host.docker.internal:11434`
- `RCA_OLLAMA_MODEL`, default `qwen2.5:3b-instruct`
- `COPILOT_OLLAMA_MODEL`, default `qwen2.5:3b-instruct`

If Ollama is not running on the host, these services can start but agent calls will fail or degrade depending on the endpoint.

## Environment Variables

Primary variables are wired through Compose and optional `.env` files:

- simulation: `SITE_ID`, `TICK_INTERVAL_SEC`, `SIM_SPEED`
- AIOps: `CONGESTION_THRESHOLD`, `SLICE_MISMATCH_CONFIDENCE_THRESHOLD`, `SLA_RISK_THRESHOLD`, `MODEL_POLL_INTERVAL_SEC`
- ports: `REDIS_PORT`, `API_PORT`, `VES_PORT`, `NETCONF_PORT`, `FAULT_ENGINE_PORT`, `GRAFANA_PORT`, `DASHBOARD_FRONTEND_PORT`, `DASHBOARD_KONG_PORT`, `RCA_AGENT_PORT`, `COPILOT_AGENT_PORT`
- MLOps: `MLOPS_POSTGRES_*`, `MINIO_*`, `MLFLOW_*`, `AWS_*`, `MLOPS_API_PORT`, `MLOPS_LOG_MONITORING_MODE`, `KIBANA_PORT`
- dashboard: `DASHBOARD_JWT_SECRET`, `DASHBOARD_DATA_PROVIDER` (default `bff`)
- MLOps Operations Center (dashboard-backend + mlops-runner): `MLOPS_PIPELINE_ENABLED` (default `true`), `MLOPS_ORCHESTRATION_TIMEOUT_SECONDS` (default `7200`), `MLOPS_RUNNER_TOKEN` (optional shared secret), `MLOPS_TOOLS_*_URL` (default `http://localhost:*` so the browser opens host-published UIs)
- drift-monitor (mlops-tier): `DRIFT_ANOMALY_THRESHOLD`, `DRIFT_WINDOW_SECONDS`, `DRIFT_COOLDOWN_SECONDS`, `DRIFT_POLL_INTERVAL_SECONDS`
- agentic: `OLLAMA_BASE_URL`, `RCA_OLLAMA_MODEL`, `COPILOT_OLLAMA_MODEL`

## Common Operations

Stop containers:

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

- Local-development credentials are present in Compose and should not be used as production secrets.
- `mlops-worker` is manual and does not start during `docker compose --profile mlops up --build`.
- The aiops-tier `drift-monitor` (statistical, alibi-detect) requires the `drift` profile; the mlops-tier `drift-monitor` (anomaly-count based) is part of the default runtime.
- AIOps model-backed inference requires promoted artifacts to exist locally under `batch-orchestrator/models/promoted/`.
