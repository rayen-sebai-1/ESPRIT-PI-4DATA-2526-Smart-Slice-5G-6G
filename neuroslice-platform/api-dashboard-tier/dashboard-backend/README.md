# Dashboard Backend

PostgreSQL-backed dashboard service for protected NeuroSlice UI metadata, plus a provider abstraction for operational dashboard data.

## Responsibilities

- validates access JWTs against persisted sessions in schema `auth`
- stores dashboard-owned metadata in schema `dashboard`
- exposes the protected dashboard, session, prediction, bookmark, preference, and alert-acknowledgement APIs
- keeps operational data behind a provider abstraction:
  - `temporary_mock` for Scenario B transition
  - `bff` for future `api-bff-service` integration

## Public Routes Through Kong

- `GET /api/dashboard/national`
- `GET /api/dashboard/region/{regionId}`
- `GET /api/dashboard/sessions`
- `GET /api/dashboard/sessions/{sessionId}`
- `GET /api/dashboard/predictions`
- `GET /api/dashboard/predictions/{sessionId}`
- `POST /api/dashboard/predictions/run/{sessionId}`
- `POST /api/dashboard/predictions/run-batch`
- `GET /api/dashboard/models`
- `GET|PUT /api/dashboard/preferences/me`
- `GET|POST|DELETE /api/dashboard/bookmarks`
- `POST /api/dashboard/alerts/{alertKey}/acknowledge`

## Required Environment Variables

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `DASHBOARD_DATA_PROVIDER`
- `API_BFF_BASE_URL` when `DASHBOARD_DATA_PROVIDER=bff`

## Migrations

```bash
cd neuroslice-platform/api-dashboard-tier/dashboard-backend
alembic upgrade head
```
