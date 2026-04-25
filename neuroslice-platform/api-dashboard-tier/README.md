# API Dashboard Tier

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
- `/admin/users`: `ADMIN`

That means `NETWORK_MANAGER` is allowed by the backend prediction API but does not currently get a predictions route in the shipped frontend.

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
