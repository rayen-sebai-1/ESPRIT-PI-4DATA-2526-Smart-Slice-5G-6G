# API Dashboard Tier

The API dashboard tier is the user-facing access layer for NeuroSlice. It contains one public telemetry BFF, one protected dashboard stack, the Kong gateway in front of the protected APIs, and the React dashboard UI.

## What Is In This Folder

| Path | Stack | Purpose |
| --- | --- | --- |
| `api-bff-service/` | FastAPI, Redis, HTTPX | Public BFF for KPIs, AIOps outputs, scenario and fault control, SSE, and ML export views |
| `auth-service/` | FastAPI, SQLAlchemy, Alembic, PyJWT, Argon2 | Authentication, refresh/session lifecycle, user administration, audit logs |
| `dashboard-backend/` | FastAPI, SQLAlchemy, Alembic, HTTPX | Protected dashboard domain API, metadata persistence, provider abstraction |
| `kong-gateway/` | Kong declarative config | Browser-facing gateway for `/api/auth/*` and `/api/dashboard/*` |
| `react-dashboard/` | React 18, Vite 5, Tailwind CSS, React Query, Axios, Recharts | Protected operations dashboard UI |

## Runtime Architecture

```text
Browser
  -> react-dashboard (localhost:5173)
  -> /api/* proxied to kong-gateway (localhost:8008)
  -> auth-service and dashboard-backend on the internal Docker network

External/API clients
  -> api-bff-service (localhost:8000)

dashboard-backend
  -> PostgreSQL schemas: auth + dashboard
  -> api-bff-service when DASHBOARD_DATA_PROVIDER=bff

auth-service
  -> PostgreSQL schema: auth

api-bff-service
  -> Redis entity state and streams
  -> fault-engine
```

Current default protected UI flow:

```text
react-dashboard -> kong-gateway -> auth-service
react-dashboard -> kong-gateway -> dashboard-backend -> temporary_mock provider
```

## Current Frontend Surface

The React app currently contains these routes:

- `/login`
- `/dashboard/national`
- `/dashboard/region`
- `/dashboard/region/:regionId`
- `/sessions`
- `/predictions`
- `/admin/users`
- `*` -> not found page

Current role access:

| Role | Default route | Access |
| --- | --- | --- |
| `ADMIN` | `/admin/users` | All pages |
| `NETWORK_OPERATOR` | `/dashboard/national` | National dashboard, regional dashboard, sessions, predictions |
| `NETWORK_MANAGER` | `/dashboard/national` | National dashboard, regional dashboard |
| `DATA_MLOPS_ENGINEER` | `/predictions` | Predictions only |

Current UI modules include:

- national dashboard with KPI cards, region load chart, and Tunisia map
- regional dashboard with regional drill-down, charts, and session links
- sessions monitor with search, region/risk/slice filters, pagination, and session detail drawer
- predictions center with filters, model catalog, ranking tabs, and single-session rerun
- admin users management for non-admin role creation and lifecycle operations

## API Surface

### Public BFF (`api-bff-service`)

These routes are served directly by the BFF and are not fronted by Kong:

- `GET /health`
- `GET /config`
- `GET /api/v1/kpis/latest`
- `GET /api/v1/kpis/recent`
- `GET /api/v1/kpis/entity/{entity_id}`
- `GET /api/v1/aiops/congestion/latest`
- `GET /api/v1/aiops/sla/latest`
- `GET /api/v1/aiops/slice-classification/latest`
- `GET /api/v1/aiops/events/recent`
- `GET /api/v1/stream/kpis`
- `GET /api/v1/faults/active`
- `POST /api/v1/scenarios/start`
- `POST /api/v1/scenarios/stop`
- `POST /api/v1/faults/inject`
- `GET /api/v1/export/sla`
- `GET /api/v1/export/slice-classifier`
- `GET /api/v1/export/congestion-sequences`

### Protected Routes Exposed Through Kong

Auth routes:

- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/auth/users`
- `POST /api/auth/users`
- `PATCH /api/auth/users/{userId}`
- `DELETE /api/auth/users/{userId}`

Dashboard routes:

- `GET /api/dashboard/national`
- `GET /api/dashboard/region/{regionId}`
- `GET /api/dashboard/sessions`
- `GET /api/dashboard/sessions/{sessionId}`
- `GET /api/dashboard/predictions`
- `GET /api/dashboard/predictions/{sessionId}`
- `POST /api/dashboard/predictions/run/{sessionId}`
- `POST /api/dashboard/predictions/run-batch`
- `GET /api/dashboard/models`
- `GET /api/dashboard/preferences/me`
- `PUT /api/dashboard/preferences/me`
- `GET /api/dashboard/bookmarks`
- `POST /api/dashboard/bookmarks`
- `DELETE /api/dashboard/bookmarks?bookmark_id=...`
- `POST /api/dashboard/alerts/{alertKey}/acknowledge`

Internal/direct service health routes:

- `auth-service`: `GET /health`
- `dashboard-backend`: `GET /health`

Those health routes are not currently exposed by Kong.

## Persistence And Data Ownership

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

Redis usage:

- `api-bff-service` reads entity hashes and telemetry/AIOps streams from Redis
- protected dashboard services do not store live telemetry in PostgreSQL

Auth migration seeds these roles:

- `ADMIN`
- `NETWORK_OPERATOR`
- `NETWORK_MANAGER`
- `DATA_MLOPS_ENGINEER`

## Dashboard Provider Modes

`dashboard-backend` supports two provider modes:

- `temporary_mock`
  - default mode in `docker-compose.yml`
  - fully implements national dashboard, regional dashboard, sessions, predictions, reruns, and model catalog using deterministic mock data
- `bff`
  - reads live national summary inputs from `api-bff-service`
  - currently supports national overview aggregation and `/models`
  - currently returns `501 Not Implemented` for regional dashboards, sessions, prediction detail, reruns, and batch prediction execution

## Environment Variables

### `api-bff-service`

Read via `ingestion-tier/shared/config.py`:

- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_DB`
- `STREAM_MAXLEN`
- `TICK_INTERVAL_SEC`
- `SIM_SPEED`
- `SERVICE_NAME`
- `SITE_ID`
- `VES_ADAPTER_URL`
- `NETCONF_ADAPTER_URL`
- `NORMALIZER_URL`
- `FAULT_ENGINE_URL`
- `METRICS_PORT`

### `auth-service`

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `JWT_ACCESS_TOKEN_EXPIRES_MINUTES` default `15`
- `JWT_REFRESH_TOKEN_EXPIRES_DAYS` default `7`
- `ARGON2_MEMORY_COST` default `65536`
- `ARGON2_TIME_COST` default `3`
- `ARGON2_PARALLELISM` default `4`
- `REFRESH_COOKIE_NAME` default `neuroslice_refresh_token`
- `REFRESH_COOKIE_PATH` default `/api/auth`
- `REFRESH_COOKIE_SECURE` default `false`
- `REFRESH_COOKIE_SAMESITE` default `lax`

Bootstrap script variables:

- `INITIAL_ADMIN_FULL_NAME`
- `INITIAL_ADMIN_EMAIL`
- `INITIAL_ADMIN_PASSWORD`
- `INITIAL_ADMIN_ROLE` default `ADMIN`

### `dashboard-backend`

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `DASHBOARD_DATA_PROVIDER` default `temporary_mock`
- `API_BFF_BASE_URL` required only when `DASHBOARD_DATA_PROVIDER=bff`

### `react-dashboard`

- `VITE_DEV_PROXY_TARGET` default `http://localhost:8008` for local Vite dev
- `VITE_AUTH_API_URL` default `/api/auth`
- `VITE_DASHBOARD_API_URL` default `/api/dashboard`
- `VITE_SESSION_API_URL` optional override for session requests
- `VITE_PREDICTION_API_URL` optional override for prediction requests

### Compose-Level Variables Used In `infrastructure/docker-compose.yml`

- `API_PORT` default `8000`
- `DASHBOARD_POSTGRES_PORT` default `5432`
- `DASHBOARD_KONG_PORT` default `8008`
- `DASHBOARD_FRONTEND_PORT` default `5173`
- `DASHBOARD_POSTGRES_DB` default `neuroslice_dashboard`
- `DASHBOARD_POSTGRES_SUPERUSER` default `neuroslice`
- `DASHBOARD_POSTGRES_SUPERPASS`
- `AUTH_DB_USER` default `auth_app`
- `AUTH_DB_PASSWORD`
- `DASHBOARD_DB_USER` default `dashboard_app`
- `DASHBOARD_DB_PASSWORD`
- `DASHBOARD_JWT_SECRET`

## Running The Tier

The end-to-end runtime for this tier lives in `../infrastructure/docker-compose.yml`.

Start the full platform:

```bash
cd neuroslice-platform/infrastructure
docker compose up --build
```

Start only the API dashboard tier services:

```bash
cd neuroslice-platform/infrastructure
docker compose up --build postgres api-bff-service auth-service dashboard-backend kong-gateway react-dashboard
```

Default compose ports:

- BFF API: `http://localhost:8000`
- PostgreSQL: `localhost:5432`
- Kong gateway: `http://localhost:8008`
- React dashboard: `http://localhost:5173`

Notes:

- `auth-service` and `dashboard-backend` are internal-only in Compose and are intended to be reached through Kong from the browser.
- `react-dashboard` proxies `/api/*` to Kong.
- `api-bff-service` depends on Redis and fault-engine, and is most practical to run through the infrastructure Compose file.

## Startup Bootstrap

`auth-service` now waits for PostgreSQL, runs `alembic upgrade head`, optionally seeds the initial admin from `INITIAL_ADMIN_*`, and then starts FastAPI.

`dashboard-backend` now waits for PostgreSQL, waits for `auth-service` to finish its bootstrap, runs `alembic upgrade head`, and then starts FastAPI.

The bootstrap is idempotent:

- `alembic upgrade head` is safe to run on every container start
- `seed_admin.py` creates the initial admin once and updates the same account on later starts instead of duplicating users

Manual fallback commands remain available:

```bash
cd neuroslice-platform/infrastructure
docker compose exec auth-service alembic upgrade head
docker compose exec dashboard-backend alembic upgrade head
docker compose exec -e INITIAL_ADMIN_FULL_NAME="Admin NeuroSlice" -e INITIAL_ADMIN_EMAIL="admin@neuroslice.tn" -e INITIAL_ADMIN_PASSWORD="change-me-now" auth-service python scripts/seed_admin.py
```

## Local Frontend Development

If Kong is already running, the frontend can also be started locally:

```bash
cd neuroslice-platform/api-dashboard-tier/react-dashboard
npm ci
npm run dev
```

By default Vite proxies `/api/*` to `http://localhost:8008`.

## Validation Checklist

Before starting, set `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` in `infrastructure/.env` if you want the auth container to create the first admin automatically.

1. Validate Compose:

```bash
cd neuroslice-platform/infrastructure
docker compose config
```

2. Start the protected dashboard stack:

```bash
cd neuroslice-platform/infrastructure
docker compose up --build postgres auth-service dashboard-backend kong-gateway react-dashboard
```

3. Verify Kong health:

```bash
cd neuroslice-platform/infrastructure
docker compose exec kong-gateway kong health
```

4. Verify auth-service health:

```bash
cd neuroslice-platform/infrastructure
docker compose exec auth-service python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read().decode())"
```

5. Verify dashboard-backend health:

```bash
cd neuroslice-platform/infrastructure
docker compose exec dashboard-backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read().decode())"
```

6. Login through Kong and keep the refresh cookie:

```bash
curl -i -c .cookies.txt -H "Content-Type: application/json" -d '{"email":"admin@example.com","password":"change-me-admin-password"}' http://localhost:8008/api/auth/login
```

Copy the `access_token` value from the JSON response into `ACCESS_TOKEN`.

7. Confirm `/api/auth/me` rejects anonymous requests:

```bash
curl -i http://localhost:8008/api/auth/me
```

8. Confirm `/api/auth/me` succeeds with a valid bearer token:

```bash
curl -i -H "Authorization: Bearer $ACCESS_TOKEN" http://localhost:8008/api/auth/me
```

9. Confirm dashboard APIs reject anonymous requests:

```bash
curl -i http://localhost:8008/api/dashboard/national
```

10. Confirm dashboard APIs succeed with a valid bearer token:

```bash
curl -i -H "Authorization: Bearer $ACCESS_TOKEN" http://localhost:8008/api/dashboard/national
```

11. Verify the database users and grants:

```bash
cd neuroslice-platform/infrastructure
docker compose exec postgres psql -U "${DASHBOARD_POSTGRES_SUPERUSER:-neuroslice}" -d "${DASHBOARD_POSTGRES_DB:-neuroslice_dashboard}" -c "SELECT grantee, table_schema, array_agg(DISTINCT privilege_type ORDER BY privilege_type) AS privileges FROM information_schema.role_table_grants WHERE grantee IN ('auth_app', 'dashboard_app') GROUP BY grantee, table_schema ORDER BY grantee, table_schema;"
```

## Folder Map

```text
api-dashboard-tier/
|-- README.md
|-- api-bff-service/
|   |-- Dockerfile
|   |-- main.py
|   `-- requirements.txt
|-- auth-service/
|   |-- alembic/
|   |-- scripts/
|   |-- Dockerfile
|   |-- main.py
|   |-- models.py
|   |-- repository.py
|   |-- schemas.py
|   |-- security.py
|   `-- service.py
|-- dashboard-backend/
|   |-- alembic/
|   |-- providers/
|   |-- Dockerfile
|   |-- main.py
|   |-- models.py
|   |-- repository.py
|   |-- schemas.py
|   |-- security.py
|   `-- service.py
|-- kong-gateway/
|   |-- Dockerfile
|   |-- kong.yml
|   `-- README.md
`-- react-dashboard/
    |-- Dockerfile
    |-- package.json
    |-- vite.config.ts
    `-- src/
```
