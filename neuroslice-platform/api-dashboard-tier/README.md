# API Dashboard Tier

Last verified: 2026-04-26.

The API dashboard tier is the user-facing access layer for NeuroSlice. It combines a public telemetry BFF with a protected dashboard stack built from auth, backend, gateway, and frontend services.

## Components

- `api-bff-service/`: public FastAPI service for KPIs, AIOps outputs, SSE, faults, scenarios, and export views
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
- server-sent events stream
- fault and scenario proxy endpoints
- feature-view export endpoints for the MLOps project

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
- `/predictions`: `ADMIN`, `NETWORK_OPERATOR`, `DATA_MLOPS_ENGINEER`
- `/mlops`, `/mlops/models`, `/mlops/runs`, `/mlops/artifacts`, `/mlops/promotions`, `/mlops/monitoring`: `ADMIN`, `DATA_MLOPS_ENGINEER`, `NETWORK_MANAGER` (read-only for `NETWORK_MANAGER`)
- `/admin/users`: `ADMIN`

That means `NETWORK_MANAGER` is allowed by the backend prediction API but does not currently get a predictions route in the shipped frontend.

## MLOps Control Center

`/api/dashboard/mlops/*` exposes a read-mostly facade over the MLOps platform:

- `GET /api/dashboard/mlops/overview`
- `GET /api/dashboard/mlops/models`
- `GET /api/dashboard/mlops/models/{model_name}`
- `GET /api/dashboard/mlops/runs`
- `GET /api/dashboard/mlops/artifacts`
- `GET /api/dashboard/mlops/promotions`
- `GET /api/dashboard/mlops/monitoring/predictions`
- `POST /api/dashboard/mlops/promote`
- `POST /api/dashboard/mlops/rollback`
- `GET /api/dashboard/mlops/tools`
- `GET /api/dashboard/mlops/tools/health`
- `POST /api/dashboard/mlops/pipeline/run`
- `GET /api/dashboard/mlops/pipeline/runs`
- `GET /api/dashboard/mlops/pipeline/runs/{run_id}`
- `GET /api/dashboard/mlops/pipeline/runs/{run_id}/logs`

`dashboard-backend` reads `models/registry.json` and `models/promoted/*/current/metadata.json` from a read-only volume mount, queries Elasticsearch (when `ES_HOST` is configured) for prediction monitoring, and delegates `promote` / `rollback` to `MLOPS_API_BASE_URL`. No MinIO secrets, MLflow database credentials, or JWT secrets are exposed to the browser.

Role access:

- read endpoints: `ADMIN`, `DATA_MLOPS_ENGINEER`, `NETWORK_MANAGER`
- `promote`, `rollback`, `pipeline/run`: `ADMIN`, `DATA_MLOPS_ENGINEER`

## MLOps Operations Center

The Operations tab under `/mlops/operations` opens external observability/MLOps UIs (MLflow, MinIO, Kibana, InfluxDB, Grafana, MLOps API), shows their health, lists pipeline run history, and exposes a single button that triggers the offline MLOps pipeline.

The pipeline trigger does **not** run any code in `dashboard-backend`. Instead it:

1. inserts a `dashboard.mlops_pipeline_runs` row with `RUNNING`
2. delegates to an internal-only `mlops-runner` service (no published port, no public route) that owns the Docker socket and executes the fixed compose command
3. captures stdout/stderr, redacts secrets, truncates, and stores the result on the same row

`mlops-runner` is the only service in the platform that can spawn the offline pipeline, and it accepts no parameters from the frontend.

## Provider Modes

`dashboard-backend` supports two provider modes:

- `temporary_mock`
  - current default in `infrastructure/docker-compose.yml`
  - provides deterministic national, regional, session, prediction, model, bookmark, preference, and alert data for UI development
- `bff`
  - aggregates live data from `api-bff-service`
  - currently supports the national overview and models catalog
  - still returns `501 Not Implemented` for the rest of the dashboard domain

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
- `dashboard-backend` provider: `temporary_mock`

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
