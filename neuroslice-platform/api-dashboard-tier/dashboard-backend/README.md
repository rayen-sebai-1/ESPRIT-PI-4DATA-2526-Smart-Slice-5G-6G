# Dashboard Backend

Last verified: 2026-04-30.

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
- `GET /metrics`
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
- `GET /mlops/drift`
- `GET /mlops/drift/{model_name}`
- `GET /mlops/drift-events`
- `GET /mlops/evaluation`
- `GET /mlops/evaluation/{model_name}`
- `POST /mlops/promote`
- `POST /mlops/rollback`
- `GET /mlops/tools`
- `GET /mlops/tools/health`
- `GET /mlops/pipeline/config`
- `POST /mlops/pipeline/run`
- `GET /mlops/pipeline/runs`
- `GET /mlops/pipeline/runs/{run_id}`
- `GET /mlops/pipeline/runs/{run_id}/logs`
- `GET /mlops/requests`
- `GET /mlops/requests/{request_id}`
- `POST /mlops/requests/{request_id}/approve`
- `POST /mlops/requests/{request_id}/reject`
- `POST /mlops/requests/{request_id}/execute`
- `GET /controls/actions`
- `GET /controls/actions/{action_id}`
- `POST /controls/actions/{action_id}/approve`
- `POST /controls/actions/{action_id}/reject`
- `POST /controls/actions/{action_id}/execute`
- `GET /controls/actuations`
- `GET /controls/actuations/{action_id}`
- `GET /runtime/services`
- `GET /runtime/services/{service_name}`
- `PATCH /runtime/services/{service_name}`

Browser-facing equivalents are exposed by Kong under `/api/dashboard/*`.

## Role Access

Backend API role checks:

- dashboard views: `ADMIN`, `NETWORK_OPERATOR`, `NETWORK_MANAGER`
- prediction views and model catalog: `ADMIN`, `NETWORK_OPERATOR`, `NETWORK_MANAGER`, `DATA_MLOPS_ENGINEER`
- rerun actions: `ADMIN`, `NETWORK_OPERATOR`
- MLOps read views (`/mlops/*` GET, including `/mlops/tools`, `/mlops/tools/health`, `/mlops/pipeline/config`, `/mlops/pipeline/runs`, `/mlops/pipeline/runs/{id}/logs`): `ADMIN`, `DATA_MLOPS_ENGINEER`, `NETWORK_MANAGER`
- MLOps write actions (`POST /mlops/promote`, `POST /mlops/rollback`, `POST /mlops/pipeline/run`): `ADMIN`, `DATA_MLOPS_ENGINEER`
- retraining requests read (`GET /mlops/requests`, `GET /mlops/requests/{id}`): `ADMIN`, `DATA_MLOPS_ENGINEER`, `NETWORK_MANAGER`
- retraining approve/reject/execute (`POST /mlops/requests/{id}/approve`, `.../reject`, `.../execute`): `ADMIN`, `DATA_MLOPS_ENGINEER`
- runtime read (`GET /runtime/services*`): `ADMIN`, `NETWORK_MANAGER`, `NETWORK_OPERATOR`, `DATA_MLOPS_ENGINEER`
- runtime write (`PATCH /runtime/services/{service_name}`): `ADMIN`, `DATA_MLOPS_ENGINEER`, `NETWORK_OPERATOR` (operational AIOps toggles only)

Current UI behavior:

- the backend accepts `NETWORK_MANAGER` on prediction endpoints
- the shipped React router also exposes `/predictions` to `NETWORK_MANAGER`

## Provider Modes

### `temporary_mock`

- not default in `infrastructure/docker-compose.yml`
- deterministic mock data for UI development
- supports national, regional, sessions, predictions, models, bookmarks, preferences, and alert acknowledgements

### `bff`

- uses `API_BFF_BASE_URL`
- default in `infrastructure/docker-compose.yml`
- supports national + regional views, sessions list/detail, predictions list/detail, and model catalog through `api-bff-service`
- live-mode rerun/batch actions are explicit `422` responses (not `501`) to indicate Scenario B read-oriented BFF behavior

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
- `MLOPS_PIPELINE_ENABLED` (default `true` in integrated Compose) - kill switch for `POST /mlops/pipeline/run`
- `MLOPS_PIPELINE_COMMAND` - label only; the actual command is fixed inside `mlops-runner`
- `MLOPS_PIPELINE_TIMEOUT_SECONDS` (default `7200`)
- `MLOPS_RUNNER_URL` (default `http://mlops-runner:8020` in Compose)
- `MLOPS_RUNNER_TOKEN` (optional shared secret - both `dashboard-backend` and `mlops-runner` must set the same value)
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB` for runtime service flags (`runtime:service:*`)

`MLOPS_PIPELINE_ENABLED` controls dashboard trigger eligibility and `GET /mlops/pipeline/config`. Actual command execution is still enforced in `mlops-runner` by `MLOPS_ORCHESTRATION_ENABLED`.

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

## Retraining Requests

`/mlops/requests` exposes the human-approval gate for all retraining triggers (anomaly-stream, Kafka drift.alert, cron scheduler).

Each request carries:

- `trigger_type`: `DRIFT` | `SCHEDULED` | `MANUAL`
- `severity`: `LOW` | `MEDIUM` | `HIGH` | `CRITICAL` (null for non-Kafka triggers)
- `drift_score`: float (null for non-drift triggers)
- `p_value`: float (null for non-statistical triggers)
- `request_source`: `mlops-drift-monitor` | `kafka/drift.alert` | `cron-scheduler`
- `status`: `pending_approval` → `approved` / `rejected` → `running` → `completed` / `failed`

State transitions: only `approved` requests can be executed; `rejected` is a terminal state. Duplicate detection prevents creating a second request for a model that already has a pending/approved request. Per-model cooldown is enforced at execution time.

## MLOps Operations Center

The `/mlops/tools`, `/mlops/tools/health`, and `/mlops/pipeline/*` routes are the dashboard-side surface of the MLOps Operations Center.

- `GET /mlops/tools` returns the configured external UIs (MLflow, MinIO, Kibana, InfluxDB, Grafana, MLOps API). The browser opens these directly via `target="_blank"` - they are not proxied.
- `GET /mlops/tools/health` checks the same services in parallel from inside the container network and reports `UP|DOWN|UNKNOWN` with latency.
- `POST /mlops/pipeline/run` creates a `dashboard.mlops_pipeline_runs` row, kicks off a FastAPI background task that calls the internal `mlops-runner` service (`POST /run-action` with fixed payload `{action:"full_pipeline", trigger_source:"manual", parameters:{}}`), and returns `RUNNING` immediately. The background task captures stdout/stderr, runs them through a redactor (passwords, tokens, secrets, JWTs, AWS keys, DB URLs), truncates to ~200 KB and persists the result.
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
