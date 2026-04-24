# Dashboard Backend

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

Browser-facing equivalents are exposed by Kong under `/api/dashboard/*`.

## Role Access

- dashboard views: `ADMIN`, `NETWORK_OPERATOR`, `NETWORK_MANAGER`
- prediction views: `ADMIN`, `NETWORK_OPERATOR`, `NETWORK_MANAGER`, `DATA_MLOPS_ENGINEER`
- rerun actions: `ADMIN`, `NETWORK_OPERATOR`

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

## Local Commands

Run migrations manually:

```bash
cd neuroslice-platform/api-dashboard-tier/dashboard-backend
alembic upgrade head
```

The container startup script already waits for PostgreSQL, runs migrations, and then starts Uvicorn.
