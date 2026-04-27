# Dashboard Backend

Last verified: 2026-04-26.

`dashboard-backend` is the protected dashboard domain API. It validates authenticated sessions against the shared PostgreSQL database, stores dashboard-owned metadata, and delegates operational views to a pluggable provider layer.

## Responsibilities

- validates access tokens against active sessions in schema `auth`
- stores dashboard metadata in schema `dashboard`
- serves national and regional dashboard views
- serves session and prediction APIs for the frontend
- stores preferences, bookmarks, and alert acknowledgements
- switches between `temporary_mock` and `bff` provider modes

## Direct Internal Routes

- `GET /health`
- `GET /dashboard/national`
- `GET /dashboard/region/{region_id}`
- `GET /dashboard/preferences/me`
- `PUT /dashboard/preferences/me`
- `GET /dashboard/bookmarks`
- `POST /dashboard/bookmarks`
- `DELETE /dashboard/bookmarks`
- `POST /dashboard/alerts/{alert_key}/acknowledge`
- `GET /sessions`
- `GET /sessions/{session_id}`
- `GET /predictions`
- `GET /predictions/{session_id}`
- `POST /predictions/run/{session_id}`
- `POST /predictions/run-batch`
- `GET /models`
- `GET /mlops/overview`
- `GET /mlops/models`
- `GET /mlops/models/{model_name}`
- `GET /mlops/runs`
- `GET /mlops/artifacts`
- `GET /mlops/promotions`
- `GET /mlops/monitoring/predictions`
- `POST /mlops/promote`
- `POST /mlops/rollback`
- `GET /mlops/tools`
- `GET /mlops/tools/health`
- `POST /mlops/pipeline/run`
- `GET /mlops/pipeline/runs`
- `GET /mlops/pipeline/runs/{run_id}`
- `GET /mlops/pipeline/runs/{run_id}/logs`

Browser-facing equivalents are exposed by Kong under `/api/dashboard/*`.

## Role Access

Backend API role checks:

- dashboard views: `ADMIN`, `NETWORK_OPERATOR`, `NETWORK_MANAGER`
- prediction views and model catalog: `ADMIN`, `NETWORK_OPERATOR`, `NETWORK_MANAGER`, `DATA_MLOPS_ENGINEER`
- rerun actions: `ADMIN`, `NETWORK_OPERATOR`
- MLOps read views (`/mlops/*` GET, including `/mlops/tools`, `/mlops/tools/health`, `/mlops/pipeline/runs`, `/mlops/pipeline/runs/{id}/logs`): `ADMIN`, `DATA_MLOPS_ENGINEER`, `NETWORK_MANAGER`
- MLOps write actions (`POST /mlops/promote`, `POST /mlops/rollback`, `POST /mlops/pipeline/run`): `ADMIN`, `DATA_MLOPS_ENGINEER`

Current UI difference:

- the backend accepts `NETWORK_MANAGER` on prediction endpoints
- the shipped React router does not currently expose a `/predictions` route to `NETWORK_MANAGER`

## Provider Modes

### `temporary_mock`

- default in `infrastructure/docker-compose.yml`
- deterministic mock data for UI development
- supports national, regional, sessions, predictions, models, bookmarks, preferences, and alert acknowledgements

### `bff`

- uses `API_BFF_BASE_URL`
- currently supports national overview aggregation and a simple models catalog
- still returns `501 Not Implemented` for regional, session, prediction detail, and batch execution workflows

## Stored Metadata

Schema `dashboard` contains:

- `dashboard_preferences`
- `dashboard_bookmarks`
- `alert_acknowledgements`
- `mlops_pipeline_runs` (run history of the offline MLOps pipeline)

The service also reads these auth tables through a read model:

- `auth.roles`
- `auth.users`
- `auth.user_sessions`

## Key Environment Variables

- `DATABASE_URL`
- `PORT`
- `JWT_SECRET_KEY`
- `DASHBOARD_DATA_PROVIDER`
- `API_BFF_BASE_URL` when `DASHBOARD_DATA_PROVIDER=bff`
- `MLOPS_API_BASE_URL`
- `MLFLOW_TRACKING_URI`
- `MLOPS_MODELS_DIR` (defaults to `/mlops/models`, read-only mount of `mlops-tier/batch-orchestrator/models`)
- `ES_HOST` and `ES_INDEX_NAME` for the prediction monitoring read endpoint (Elasticsearch)
- `MLOPS_TOOLS_MLFLOW_URL`, `MLOPS_TOOLS_MINIO_URL`, `MLOPS_TOOLS_KIBANA_URL`, `MLOPS_TOOLS_INFLUXDB_URL`, `MLOPS_TOOLS_GRAFANA_URL`, `MLOPS_TOOLS_MLOPS_API_URL` for the tool inventory shown in the MLOps Operations Center
- `MLOPS_TOOLS_*_HEALTH_URL` (optional, defaults are container-internal probes; useful when the dashboard runs outside Compose)
- `MLOPS_PIPELINE_ENABLED` (default `false`) - kill switch for `POST /mlops/pipeline/run`
- `MLOPS_PIPELINE_COMMAND` - label only; the actual command is fixed inside `mlops-runner`
- `MLOPS_PIPELINE_TIMEOUT_SECONDS` (default `7200`)
- `MLOPS_RUNNER_URL` (default `http://mlops-runner:8020` in Compose)
- `MLOPS_RUNNER_TOKEN` (optional shared secret - both `dashboard-backend` and `mlops-runner` must set the same value)

`DASHBOARD_DATA_PROVIDER` and `API_BFF_BASE_URL` drive the legacy provider layer. The MLOps Control Center endpoints additionally read `MLOPS_MODELS_DIR`, optionally call `MLOPS_API_BASE_URL` for `promote` / `rollback`, and optionally query `ES_HOST` for prediction monitoring. None of these endpoints expose MinIO credentials, MLflow database credentials, or JWT secrets.

## Local Commands

Run migrations manually:

```bash
cd neuroslice-platform/api-dashboard-tier/dashboard-backend
alembic upgrade head
```

The container startup script already waits for PostgreSQL, runs migrations, and then starts Uvicorn.

## Verification

With the Compose stack running:

```bash
curl http://localhost:8002/health
curl -i http://localhost:8008/api/dashboard/national
```

`/health` should succeed on the internal service port. Dashboard API calls through Kong should require a valid dashboard access token.

## MLOps Operations Center

The `/mlops/tools`, `/mlops/tools/health`, and `/mlops/pipeline/*` routes are the dashboard-side surface of the MLOps Operations Center.

- `GET /mlops/tools` returns the configured external UIs (MLflow, MinIO, Kibana, InfluxDB, Grafana, MLOps API). The browser opens these directly via `target="_blank"` - they are not proxied.
- `GET /mlops/tools/health` checks the same services in parallel from inside the container network and reports `UP|DOWN|UNKNOWN` with latency.
- `POST /mlops/pipeline/run` creates a `dashboard.mlops_pipeline_runs` row, kicks off a FastAPI background task that calls the internal `mlops-runner` service, and returns `RUNNING` immediately. The background task captures stdout/stderr, runs them through a redactor (passwords, tokens, secrets, JWTs, AWS keys, DB URLs), truncates to ~200 KB and persists the result.
- `GET /mlops/pipeline/runs`, `/mlops/pipeline/runs/{run_id}`, `/mlops/pipeline/runs/{run_id}/logs` are read-only paginated views over the same table.

Safety properties:

- The pipeline command is fixed inside `mlops-runner` and never accepted from a request.
- `dashboard-backend` does not have direct access to the Docker socket; only `mlops-runner` does, behind an internal-only Compose network.
- `MLOPS_PIPELINE_ENABLED=false` makes `POST /mlops/pipeline/run` return `409 Conflict` regardless of role.

## Tests

```bash
cd neuroslice-platform/api-dashboard-tier/dashboard-backend
pip install -r requirements.txt pytest
pytest tests
```

The test suite covers `mlops` registry parsing, role enforcement, and the action delegation contract. It does not require PostgreSQL, MLflow, MinIO, or Elasticsearch.
