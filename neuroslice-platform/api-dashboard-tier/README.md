# API Dashboard Tier

Last verified: 2026-04-30.

The API dashboard tier is the user-facing access layer for NeuroSlice. It combines a public telemetry BFF with a protected dashboard stack built from auth, backend, gateway, and frontend services.

Scope note: Agentic AI tier is implemented in the repository but excluded from current Scenario B validation scope.

## Components

- `api-bff-service/`: public FastAPI service for KPIs, AIOps outputs, Live State, SSE, faults, scenarios, network insights, export views, drift status (`/api/v1/drift/*`), and online evaluation state (`/api/v1/evaluation/*`)
- `auth-service/`: PostgreSQL-backed authentication and user administration service
- `dashboard-backend/`: protected dashboard domain API and metadata persistence layer
- `kong-gateway/`: browser-facing API gateway for `/api/auth/*` and `/api/dashboard/*`
- `react-dashboard/`: React 18 + Vite frontend

## Runtime Architecture

```text
External/API clients -> api-bff-service (localhost:8000)

Browser -> react-dashboard (localhost:5173)
        -> kong-gateway (localhost:8008)
        -> auth-service / dashboard-backend

dashboard-backend
  -> PostgreSQL schemas auth + dashboard
  -> optional api-bff-service integration when DASHBOARD_DATA_PROVIDER=bff
```

## Public vs Protected Surfaces

### Public BFF

Served directly by `api-bff-service` on `http://localhost:8000`:

- health and config
- latest and recent KPI queries
- runtime AIOps query endpoints
- Live State endpoints (`/api/v1/live/overview`, `/api/v1/live/entities`, `/api/v1/live/entities/{entity_id}`, `/api/v1/live/entities/{entity_id}/aiops`, `/api/v1/live/faults`, `/api/v1/live/logs`, `/api/v1/live/stream`)
- network insights endpoints (`/api/v1/network/national`, `/api/v1/network/region/{region_id}`, `/api/v1/network/logs`)
- server-sent events streams
- fault and scenario proxy endpoints
- feature-view export endpoints for the MLOps project
- drift detection status endpoints: `GET /api/v1/drift/latest`, `GET /api/v1/drift/latest/{model_name}`, `GET /api/v1/drift/events`
- online evaluation endpoints: `GET /api/v1/evaluation/latest`, `GET /api/v1/evaluation/latest/{model_name}`, `GET /api/v1/evaluation/events`

### Protected Dashboard Stack

Served through Kong on `http://localhost:8008`:

- `/api/auth/*` -> `auth-service`
- `/api/dashboard/*` -> `dashboard-backend`

Direct service ports remain internal in Compose:

- `auth-service`: `8001`
- `dashboard-backend`: `8002`

## Current Role Behavior

Backend API role checks today:

- dashboard views: `ADMIN`, `NETWORK_OPERATOR`, `NETWORK_MANAGER`
- prediction APIs and model catalog: `ADMIN`, `NETWORK_OPERATOR`, `NETWORK_MANAGER`, `DATA_MLOPS_ENGINEER`
- prediction rerun actions: `ADMIN`, `NETWORK_OPERATOR`

Current React router exposure:

- `/sessions`: `ADMIN`, `NETWORK_OPERATOR`
- `/live-state`: `ADMIN`, `NETWORK_OPERATOR`
- `/predictions`: `ADMIN`, `NETWORK_OPERATOR`, `NETWORK_MANAGER`, `DATA_MLOPS_ENGINEER`
- `/mlops`, `/mlops/models`, `/mlops/runs`, `/mlops/artifacts`, `/mlops/promotions`, `/mlops/monitoring`, `/mlops/drift`, `/mlops/operations`, `/mlops/orchestration`: `ADMIN`, `DATA_MLOPS_ENGINEER`, `NETWORK_MANAGER` (read-only for `NETWORK_MANAGER`)
- `/control/actions`: `ADMIN`, `NETWORK_OPERATOR`, `NETWORK_MANAGER`
- `/agentic/root-cause`, `/agentic/copilot`: all authenticated users
- `/admin/users`: `ADMIN`

`NETWORK_MANAGER` is allowed on prediction APIs and is also included in the shipped frontend route guard for `/predictions`.

## MLOps Control Center

`/api/dashboard/mlops/*` exposes a read-mostly facade over the MLOps platform:

- `GET /api/dashboard/mlops/overview`
- `GET /api/dashboard/mlops/models`
- `GET /api/dashboard/mlops/models/{model_name}`
- `GET /api/dashboard/mlops/runs`
- `GET /api/dashboard/mlops/artifacts`
- `GET /api/dashboard/mlops/promotions`
- `GET /api/dashboard/mlops/monitoring/predictions`
- `GET /api/dashboard/mlops/drift`
- `GET /api/dashboard/mlops/drift/{model_name}`
- `GET /api/dashboard/mlops/drift-events`
- `GET /api/dashboard/mlops/evaluation`
- `GET /api/dashboard/mlops/evaluation/{model_name}`
- `POST /api/dashboard/mlops/promote`
- `POST /api/dashboard/mlops/rollback`
- `GET /api/dashboard/mlops/tools`
- `GET /api/dashboard/mlops/tools/health`
- `GET /api/dashboard/mlops/pipeline/config`
- `POST /api/dashboard/mlops/pipeline/run`
- `GET /api/dashboard/mlops/pipeline/runs`
- `GET /api/dashboard/mlops/pipeline/runs/{run_id}`
- `GET /api/dashboard/mlops/pipeline/runs/{run_id}/logs`
- `GET /api/dashboard/mlops/requests`
- `GET /api/dashboard/mlops/requests?trigger_type=SCHEDULED` (scheduler-only view)
- `GET /api/dashboard/mlops/requests?trigger_type=DRIFT` (drift-only view)
- `GET /api/dashboard/mlops/requests/{request_id}`
- `POST /api/dashboard/mlops/requests/{request_id}/approve`
- `POST /api/dashboard/mlops/requests/{request_id}/reject`
- `POST /api/dashboard/mlops/requests/{request_id}/execute`

Pending marker lifecycle (`mlops:requests:pending:*`) is lease-based:
- created when a request enters `pending_approval`
- cleared on terminal statuses (`completed`, `failed`, `skipped`, `rejected`, `timeout`, `expired`, `cancelled`)
- reconciled on backend startup and during scheduler checks to remove stale markers safely
- cleanup is idempotent and only clears model-level lease when request id matches or marker is stale/terminal

`dashboard-backend` reads `models/registry.json` and `models/promoted/*/current/metadata.json` from a read-only volume mount, queries Elasticsearch (when `ES_HOST` is configured) for prediction monitoring, and delegates `promote` / `rollback` to `MLOPS_API_BASE_URL`. No MinIO secrets, MLflow database credentials, or JWT secrets are exposed to the browser.

Role access:

- read endpoints: `ADMIN`, `DATA_MLOPS_ENGINEER`, `NETWORK_MANAGER`
- `promote`, `rollback`, `pipeline/run`: `ADMIN`, `DATA_MLOPS_ENGINEER`
- `requests` read: `ADMIN`, `DATA_MLOPS_ENGINEER`, `NETWORK_MANAGER`
- `requests/approve`, `requests/reject`, `requests/execute`: `ADMIN`, `DATA_MLOPS_ENGINEER`

## Control Actions Center

`/api/dashboard/controls/*` exposes a proxy facade over `policy-control` and `mlops-drift-monitor`:

- `GET /api/dashboard/controls/actions` -> `policy-control /actions`
- `GET /api/dashboard/controls/actions/{id}` -> `policy-control /actions/{id}`
- `POST /api/dashboard/controls/actions/{id}/approve` -> `policy-control /actions/{id}/approve`
- `POST /api/dashboard/controls/actions/{id}/reject` -> `policy-control /actions/{id}/reject`
- `POST /api/dashboard/controls/actions/{id}/execute` -> `policy-control /actions/{id}/execute`
- `GET /api/dashboard/controls/actuations` -> `policy-control /actuations`
- `GET /api/dashboard/controls/actuations/{id}` -> `policy-control /actuations/{id}`
- `GET /api/dashboard/controls/drift/status` -> `mlops-drift-monitor /drift/status`
- `GET /api/dashboard/controls/drift/events` -> `mlops-drift-monitor /drift/events`
- `POST /api/dashboard/controls/drift/trigger` -> `mlops-drift-monitor /drift/trigger`

Role access: `ADMIN`, `NETWORK_OPERATOR`, `NETWORK_MANAGER` (approve/reject/execute hidden for `NETWORK_MANAGER`).

Closed-loop note: action execution remains simulated in Scenario B. `policy-control` writes Redis actuation keys and publishes `stream:control.actuations`; no real PCF/NMS call path exists.

## Runtime Service Control

`dashboard-backend` exposes Redis-backed runtime service controls:

- `GET /api/dashboard/runtime/services`
- `GET /api/dashboard/runtime/services/{service_name}`
- `PATCH /api/dashboard/runtime/services/{service_name}`

Request body:

```json
{
  "enabled": true,
  "mode": "auto",
  "reason": "operator note"
}
```

Controlled services:

- `congestion-detector`
- `sla-assurance`
- `slice-classifier`
- `aiops-drift-monitor`
- `mlops-drift-monitor`

Role policy:

- read: `ADMIN`, `NETWORK_MANAGER`, `DATA_MLOPS_ENGINEER`, `NETWORK_OPERATOR`
- write: `ADMIN`, `DATA_MLOPS_ENGINEER`, and `NETWORK_OPERATOR` for operational AIOps toggles

## MLOps Operations Center

The Operations tab under `/mlops/operations` opens external observability/MLOps UIs (MLflow, MinIO, Kibana, InfluxDB, Grafana, MLOps API), shows their health, lists pipeline run history, and exposes a single button that triggers the offline MLOps pipeline.

The "Run Offline MLOps Pipeline" button first checks `GET /api/dashboard/mlops/pipeline/config` to read `MLOPS_PIPELINE_ENABLED`; when disabled, the UI shows the disable reason and does not fire `POST /api/dashboard/mlops/pipeline/run`.

The pipeline trigger does **not** run any code in `dashboard-backend`. Instead it:

1. inserts a `dashboard.mlops_pipeline_runs` row with `RUNNING`
2. delegates to an internal-only `mlops-runner` service (no published port, no public route) via `POST /run-action` with `{ action: "full_pipeline", trigger_source: "manual" }`
3. captures stdout/stderr, redacts secrets, truncates, and stores the result on the same row

`mlops-runner` is the only service in the platform that can spawn the offline pipeline. It is called by `dashboard-backend` only after a retraining request has been approved and explicitly executed via the dashboard. `mlops-drift-monitor` creates `pending_approval` requests but never calls `mlops-runner` directly.

## Provider Modes

`dashboard-backend` supports two provider modes:

- `bff`
  - current default in `infrastructure/docker-compose.yml`
  - aggregates live data from `api-bff-service`
- `temporary_mock`
  - provides deterministic national, regional, session, prediction, model, bookmark, preference, and alert data for UI development; useful when `api-bff-service` is not available

## Database Ownership

PostgreSQL schemas:

- `auth`
  - `roles`
  - `users`
  - `user_sessions`
  - `audit_logs`
- `dashboard`
  - `dashboard_preferences`
  - `dashboard_bookmarks`
  - `alert_acknowledgements`

## Compose Notes

Start the full platform:

```bash
cd neuroslice-platform/infrastructure
docker compose up --build
```

Start only this tier with its database:

```bash
cd neuroslice-platform/infrastructure
docker compose up --build postgres api-bff-service auth-service dashboard-backend kong-gateway react-dashboard
```

Current development defaults in the Compose file:

- seeded admin email: `admin@neuroslice.tn`
- seeded admin password: `change-me-now`
- `dashboard-backend` provider: `bff`

Replace those values before using the stack anywhere except local development.

## Local Frontend Development

If Kong is already running:

```bash
cd neuroslice-platform/api-dashboard-tier/react-dashboard
npm ci
npm run dev
```

Vite proxies `/api/*` to `http://localhost:8008` by default.

## Verification

```bash
curl http://localhost:8000/health
curl http://localhost:8008/api/auth/login -i
curl http://localhost:5173
```

The login endpoint should reject unauthenticated or malformed requests through Kong, while the React app should load and call `/api/auth/*` and `/api/dashboard/*` through the gateway.
