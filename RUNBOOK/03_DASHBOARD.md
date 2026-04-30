# 03 Dashboard

## Login and auth flow
```text
Browser -> react-dashboard (5173)
       -> Kong (8008)
       -> /api/auth/* (auth-service)
       -> /api/dashboard/* (dashboard-backend)
```

JWT/session validation is enforced by backend services (`auth-service` and `dashboard-backend`), not by Kong token verification plugins.

## Roles and permissions (effective behavior)
| Area | Roles |
|---|---|
| Dashboard read (`/dashboard/*`) | `ADMIN`, `NETWORK_OPERATOR`, `NETWORK_MANAGER` |
| Sessions page/API | `ADMIN`, `NETWORK_OPERATOR` |
| Predictions read | `ADMIN`, `NETWORK_OPERATOR`, `NETWORK_MANAGER`, `DATA_MLOPS_ENGINEER` |
| Prediction rerun/batch endpoints | `ADMIN`, `NETWORK_OPERATOR` (provider behavior may still return `422` in live mode) |
| MLOps read | `ADMIN`, `DATA_MLOPS_ENGINEER`, `NETWORK_MANAGER` |
| MLOps write (`promote`, `rollback`, `pipeline/run`) | `ADMIN`, `DATA_MLOPS_ENGINEER` |
| Control actions page | `ADMIN`, `NETWORK_OPERATOR`, `NETWORK_MANAGER` |
| Runtime services read (`/runtime/services*`) | `ADMIN`, `NETWORK_OPERATOR`, `NETWORK_MANAGER`, `DATA_MLOPS_ENGINEER` |
| Runtime services write (`PATCH /runtime/services/{name}`) | `ADMIN`, `DATA_MLOPS_ENGINEER`, `NETWORK_OPERATOR` (AIOps operational toggles) |

## Key pages
- `/live-state`: live entity/fault/state view
- `/predictions`: predictions list/detail and rerun controls (role + provider dependent)
- `/mlops/*`: models, runs, artifacts, promotions, monitoring, drift, operations, orchestration
- `/mlops/orchestration`: includes runtime service control cards
- `/control/actions`: alert-action lifecycle and simulated execution controls

## Important backend endpoints used by UI
- `GET /dashboard/national`
- `GET /dashboard/region/{region_id}`
- `GET /sessions`, `GET /sessions/{session_id}`
- `GET /predictions`, `GET /predictions/{session_id}`
- `POST /predictions/run/{session_id}`, `POST /predictions/run-batch`
- `/mlops/*` and `/controls/*` protected routes
- `/runtime/services*` protected routes

## Kong routing summary
From `kong-gateway/kong.yml`:
- `/api/auth/*` -> `auth-service`
- `/api/dashboard/*` -> `dashboard-backend`
- `/api/v1/live` -> `api-bff-service` (public live-state path)

## Provider note (`dashboard-backend`)
Default is `DASHBOARD_DATA_PROVIDER=bff` in Compose.

- In `bff` mode: national/regional/sessions/predictions read endpoints are wired to live BFF data.
- In `bff` mode: ad-hoc rerun/batch prediction operations are intentionally returned as `422` (read-oriented live mode).
