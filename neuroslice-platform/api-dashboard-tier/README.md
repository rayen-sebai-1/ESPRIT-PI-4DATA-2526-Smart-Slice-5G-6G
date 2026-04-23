# API Dashboard Tier

Client-facing API and dashboard layer for NeuroSlice. This tier exposes simulator/AIOps data to users and provides operational dashboard UX with authentication, auditability, and role-based access.

## Tier Purpose

This tier provides two complementary access surfaces:

- Platform BFF API (`api-bff-service`) for KPI, AIOps events, scenario/fault control, and ML export features.
- Protected dashboard stack (`react-dashboard` + `kong-gateway` + `auth-service` + `dashboard-backend`) for role-based operations UI.

## Subsystems

### 1) API BFF Service

Path: `api-bff-service/`

Main capabilities:

- Health/config endpoints.
- Latest and recent KPI queries.
- Per-entity telemetry lookups.
- Latest AIOps outputs and recent AIOps event stream reads.
- SSE streaming endpoint for live KPIs.
- Scenario and fault proxy endpoints (to `simulation-tier/fault-engine`).
- Export endpoints for SLA, slice-classifier, and congestion training views.

Important endpoints:

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

### 2) Dashboard Backend

Path: `dashboard-backend/`

Main capabilities:

- National and regional dashboard endpoints.
- Sessions and prediction catalog endpoints.
- Prediction execution endpoints (`/predictions/run/*`).
- Dashboard metadata persistence in PostgreSQL schema `dashboard`.
- JWT session validation against PostgreSQL-backed auth sessions.
- Provider abstraction for operational dashboard data:
  - `temporary_mock` for Scenario B transition
  - `bff` for future `api-bff-service` integration

Important note:

- `dashboard-backend/` is the canonical dashboard domain API backend.
- `common.data` and the old nested `api_service/` and `auth_service/` modules are removed.
- PostgreSQL is used only for dashboard-owned metadata, not telemetry or live KPI streams.

### 3) Auth Service

Path: `auth-service/`

Main capabilities:

- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`
- admin user management endpoints (`/users`) with admin role checks
- Argon2id password hashing, persisted sessions, refresh rotation, and audit logging in PostgreSQL schema `auth`

Authentication model:

- short-lived JWT access tokens plus `HttpOnly` refresh cookie
- session revocation enforced by checking `auth.user_sessions` on protected routes
- no JSON file persistence and no plaintext passwords

### 4) Dashboard Gateway and Frontend

- `kong-gateway/kong.yml`: declarative gateway routing
- `/api/auth/*` -> `auth-service`
- `/api/dashboard/*` -> `dashboard-backend`
- cookies are forwarded through Kong with credentialed CORS for the React origin
- internal auth/backend services are not published on host ports in Compose, so the browser-facing dashboard flow goes through Kong only

- `react-dashboard/`: canonical Vite + React + Tailwind entry
- contains the full frontend source tree and frontend build/runtime assets
- routes for login, national dashboard, regional dashboard, prediction center, admin users

## Runtime Ports (Compose Defaults)

- BFF API: `8000`
- Dashboard PostgreSQL: `5432`
- Kong Gateway: `8008`
- Frontend: `5173`
- Internal auth/backend services: Docker network only (`8000` inside the compose network)

## Running the Tier

Preferred (full connected mode):

```bash
cd neuroslice-platform/infrastructure
docker compose up --build postgres api-bff-service auth-service dashboard-backend kong-gateway react-dashboard
```

Notes:

- `api-bff-service` depends on Redis + normalizer + AIOps + fault-engine.
- `auth-service` and `dashboard-backend` both require PostgreSQL.
- `common.data` has been removed from the runtime.
- `dashboard-backend` defaults to `temporary_mock` for Scenario B and can later switch to `bff`.
- Dashboard public flow is now unambiguous: `react-dashboard` -> `kong-gateway` -> (`auth-service` or `dashboard-backend`).
- `api-bff-service` stays a separate public BFF for telemetry/AIOps/fault operations and is not used as a bypass for protected dashboard routes.

## Migrations And Bootstrap

Run migrations after PostgreSQL is healthy:

```bash
cd neuroslice-platform/api-dashboard-tier/auth-service
DATABASE_URL="postgresql+psycopg://auth_app:change-me-auth-user@localhost:5432/neuroslice_dashboard" alembic upgrade head

cd ../dashboard-backend
DATABASE_URL="postgresql+psycopg://dashboard_app:change-me-dashboard-user@localhost:5432/neuroslice_dashboard" alembic upgrade head
```

Seed the first admin account:

```bash
cd ../auth-service
DATABASE_URL="postgresql+psycopg://auth_app:change-me-auth-user@localhost:5432/neuroslice_dashboard" \
JWT_SECRET_KEY="replace-with-long-random-secret" \
INITIAL_ADMIN_FULL_NAME="Admin NeuroSlice" \
INITIAL_ADMIN_EMAIL="admin@neuroslice.tn" \
INITIAL_ADMIN_PASSWORD="change-me-now" \
python scripts/seed_admin.py
```

## Folder Map

```text
api-dashboard-tier/
├── api-bff-service/
├── auth-service/       # canonical auth entry
├── dashboard-backend/
├── kong-gateway/       # canonical gateway entry
└── react-dashboard/    # canonical frontend entry
```
