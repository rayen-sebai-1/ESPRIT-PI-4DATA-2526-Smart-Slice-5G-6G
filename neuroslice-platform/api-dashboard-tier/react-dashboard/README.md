# React Dashboard

Last verified: 2026-04-30.

`react-dashboard` is the protected React frontend for the NeuroSlice operations dashboard.

Scope note: agentic pages are implemented, but `agentic-ai-tier` is excluded from current Scenario B validation scope.

## Stack

- React 18
- Vite 5
- TypeScript
- Tailwind CSS
- TanStack Query
- Axios
- Recharts

## Runtime Model

- default UI URL: `http://localhost:5173`
- all browser API traffic goes through Kong
- access tokens are kept in memory
- refresh uses the HttpOnly refresh cookie issued by `auth-service`
- Vite proxies `/api/*` to `http://localhost:8008` by default

## Routes

- `/login`
- `/dashboard/national`
- `/dashboard/region`
- `/dashboard/region/:regionId`
- `/sessions`
- `/live-state`
- `/predictions`
- `/agentic/root-cause`
- `/agentic/copilot`
- `/control/actions`
- `/mlops`
- `/mlops/models`
- `/mlops/runs`
- `/mlops/artifacts`
- `/mlops/promotions`
- `/mlops/monitoring`
- `/mlops/drift`
- `/mlops/operations`
- `/mlops/orchestration`
- `/mlops/requests`
- `/admin/users`
- `*` -> not found page

Current route guards in the router:

- all authenticated users can access the dashboard shell
- `/sessions`: `ADMIN`, `NETWORK_OPERATOR`
- `/live-state`: `ADMIN`, `NETWORK_OPERATOR`
- `/predictions`: `ADMIN`, `NETWORK_OPERATOR`, `NETWORK_MANAGER`, `DATA_MLOPS_ENGINEER` (write/run action hidden for `NETWORK_MANAGER`)
- `/control/actions`: `ADMIN`, `NETWORK_OPERATOR`, `NETWORK_MANAGER`
- `/mlops/*`: `ADMIN`, `DATA_MLOPS_ENGINEER`, `NETWORK_MANAGER` (write actions hidden / disabled for `NETWORK_MANAGER`)
- `/admin/users`: `ADMIN`

## Topbar

The topbar displays a pulsing `DATA SOURCE: LIVE` badge when `DASHBOARD_DATA_PROVIDER=bff` is active, indicating that dashboard data is sourced from live AIOps streams rather than mock fixtures.

## MLOps Control Center

The "MLOps Control Center" sidebar entry is shown only to `ADMIN`, `DATA_MLOPS_ENGINEER`, and `NETWORK_MANAGER`. It groups ten sub-views:

- vue globale (KPI: modeles promus, quality gate pass/fail, runs en attente, sources)
- modeles (selection + detail card, metriques cles, actions valider / promouvoir / rollback / rafraichir)
- runs (derniers runs MLflow lus dans `models/registry.json`)
- artefacts (etat de `models/promoted/*/current/`)
- promotions (historique des decisions promote/reject)
- monitoring (lecture Elasticsearch `smart-slice-predictions`)
- drift (etat de drift detection Scenario B: p-value, window fill, severite, et historique des evenements)
- requests (liste des demandes de retraining en attente d'approbation: trigger type, severity, p-value, drift score; boutons approve/reject/execute pour ADMIN et DATA_MLOPS_ENGINEER)
- operations (Operations Center: liens externes, sante des services, lancement du pipeline offline, historique + logs)
- orchestration (pilotage du cycle pipeline/operations selon les droits de role + runtime service controls)

Monitoring now includes an **Online Evaluation** panel that renders rolling accuracy/precision/recall/F1 and FP/FN counters from `/api/dashboard/mlops/evaluation`.

Promote and rollback open confirmation modals before sending the action. The buttons are disabled for `NETWORK_MANAGER` because the backend rejects those calls for that role.

The Operations tab adds:

- one-click open buttons for MLflow, MinIO, Kibana, InfluxDB, Grafana, MLOps API (each link uses `target="_blank" rel="noopener noreferrer"` so the dashboard never proxies the third-party UI)
- `UP|DOWN|UNKNOWN` health badges with latency, refreshed every 30 seconds
- a confirmation-protected "Run Offline MLOps Pipeline" button (hidden / disabled for `NETWORK_MANAGER`)
- a runs table with auto-refresh while a run is `RUNNING` or `QUEUED`
- a logs modal showing redacted stdout/stderr in a monospace block, also auto-refreshing while the run is in progress

The "Run Offline MLOps Pipeline" button queries `GET /mlops/pipeline/config` on mount and disables itself with an amber notice when `MLOPS_PIPELINE_ENABLED=false`. When enabled, the action calls `POST /mlops/pipeline/run`, and run history/log views use `GET /mlops/pipeline/runs` + `GET /mlops/pipeline/runs/{run_id}/logs`.

The orchestration page also consumes runtime control APIs:

- `GET /api/dashboard/runtime/services`
- `PATCH /api/dashboard/runtime/services/{service_name}`

These toggles update Redis runtime flags only; they do not start/stop Docker containers.

Agentic features (Root Cause Agent, Copilot Agent) send requests to `/api/dashboard/agentic/*`, which is routed through Kong to `dashboard-backend` for JWT validation before proxying to the internal agent services.

## Local Development

```bash
cd neuroslice-platform/api-dashboard-tier/react-dashboard
npm ci
npm run dev
```

Build and preview:

```bash
npm run build
npm run preview
```

## Environment Variables

- `VITE_DEV_PROXY_TARGET` default `http://localhost:8008`
- `VITE_AUTH_API_URL` default `/api/auth`
- `VITE_DASHBOARD_API_URL` default `/api/dashboard`
- `VITE_SESSION_API_URL` optional override
- `VITE_PREDICTION_API_URL` optional override

## Docker Runtime

The Docker image is a multi-stage production build:

- **Stage 1 (builder)**: `node:20-alpine` — runs `npm ci` and `npm run build` to produce a static `dist/` bundle
- **Stage 2 (runner)**: `nginx:1.27-alpine` — serves the static bundle on port 5173

The nginx config (`nginx.conf`) handles:

- gzip compression and long-lived static asset caching
- `/api/` reverse proxy to `kong-gateway:8000/api/` with SSE streaming support
- SPA fallback (`try_files $uri $uri/ /index.html`) for client-side routing

## Verification

```bash
npm run build
curl http://localhost:5173
```

`npm run build` runs the TypeScript project references (`tsc -b`) and the Vite build, which is the recommended frontend smoke test for MLOps Control Center changes.

When the platform is running, browser network calls should target `/api/auth/*` and `/api/dashboard/*`; Vite forwards them to Kong at `http://localhost:8008`.
