# Scenario B Fixes

Scope: Docker Compose local prototype only. No Kubernetes, Istio, Helm, KEDA, or vLLM changes.

Date: 2026-04-29.

## Summary

Seven gaps in the Scenario B (Docker Compose) prototype were identified and fixed. Each fix is scoped, testable, and does not fake a successful outcome — operations that cannot work in Scenario B return explicit 422/409 responses with a `SCENARIO_B_LIVE_MODE` error code and a clear message.

---

## Task 1 — Agentic AI Auth Bypass

**Before:** Kong had two services routing `/api/agentic/rca/*` and `/api/agentic/copilot/*` directly to `root-cause:7005` and `copilot-agent:7006`, bypassing dashboard-backend JWT validation entirely. Any caller with network access to Kong could trigger agent workflows without a valid token.

**After:** The direct agentic Kong services have been removed. A new Kong service `dashboard-service-agentic` routes `/api/dashboard/agentic/*` → `dashboard-backend:8002/agentic`. Dashboard-backend validates the Bearer token and enforces role checks (`ADMIN`, `NETWORK_OPERATOR`, `NETWORK_MANAGER`, `DATA_MLOPS_ENGINEER`) before proxying to the internal agent services.

**Files changed:**

| File | Change |
|------|--------|
| `api-dashboard-tier/kong-gateway/kong.yml` | Removed `agentic-root-cause` and `agentic-copilot` services; added `dashboard-service-agentic` routing to dashboard-backend |
| `api-dashboard-tier/dashboard-backend/main.py` | Added `/agentic/health`, `/agentic/root-cause/manual-scan`, `/agentic/copilot/query/text`, `/agentic/copilot/query` (SSE) proxy endpoints with `require_roles` |
| `api-dashboard-tier/dashboard-backend/schemas.py` | Added `AgenticHealthResponse` schema |
| `api-dashboard-tier/react-dashboard/src/api/axios.ts` | Changed `agentClient` base URL from `/api/agentic` to `/api/dashboard/agentic` |
| `api-dashboard-tier/react-dashboard/src/api/agentApi.ts` | Updated RCA path from `/rca/manual-scan` to `/root-cause/manual-scan` |

**Verification:**
```bash
# Must return 401 (no token)
curl -i http://localhost:8008/api/dashboard/agentic/health
# Must return 200 (valid token, any agentic role)
curl -i -H "Authorization: Bearer <token>" http://localhost:8008/api/dashboard/agentic/health
```

---

## Task 2 — BFF Provider 501 Routes

**Before:** `BffDashboardProvider` returned HTTP 501 for `get_region_dashboard`, `list_sessions`, `get_session`, `list_predictions`, `get_prediction`, `run_prediction`, and `run_batch`. Setting `DASHBOARD_DATA_PROVIDER=bff` made the regional dashboard, sessions monitor, and predictions center unusable.

**After:**
- `get_region_dashboard`: calls `/api/v1/network/region/{domain}` via the BFF service and maps the response to `RegionalDashboard`.
- `list_sessions`: calls `/api/v1/kpis/latest`, maps Redis KPI entities to `SessionSummary` with pagination and region/status filtering.
- `get_session`: searches the sessions list by id.
- `list_predictions`: joins congestion, SLA, and classification scores into `PredictionResponse` rows.
- `get_prediction`: searches predictions by session_id.
- `run_prediction` / `run_batch`: return HTTP 422 with error code `SCENARIO_B_LIVE_MODE` and a clear message explaining that on-demand re-scoring is not available in live BFF mode. This is intentional — the scores are already live and re-triggering them has no meaning in this architecture.

**Files changed:**

| File | Change |
|------|--------|
| `api-dashboard-tier/dashboard-backend/providers/bff.py` | Replaced five `_not_supported()` stubs with live BFF data implementations |

**Verification:**
```bash
# Regional dashboard (requires DASHBOARD_DATA_PROVIDER=bff)
curl -H "Authorization: Bearer <token>" http://localhost:8008/api/dashboard/dashboard/region/1
# Sessions list
curl -H "Authorization: Bearer <token>" http://localhost:8008/api/dashboard/sessions
# Predictions list
curl -H "Authorization: Bearer <token>" http://localhost:8008/api/dashboard/predictions
# run_prediction returns 422 with SCENARIO_B_LIVE_MODE
curl -X POST -H "Authorization: Bearer <token>" http://localhost:8008/api/dashboard/predictions/1/run
```

---

## Task 3 — NETWORK_MANAGER Prediction Route Mismatch

**Before:** The backend `prediction_reader_roles` already included `NETWORK_MANAGER` (read access only), but the React router protected `/predictions` with `["ADMIN", "NETWORK_OPERATOR", "DATA_MLOPS_ENGINEER"]`. NETWORK_MANAGER users got a redirect/forbidden page despite valid backend permissions. The nav sidebar also hid the entry for that role.

**After:** Router and nav constants updated to include `NETWORK_MANAGER`. The `PredictionsTable` and `PredictionsCenterPage` hide the "Relancer" button when the user is not ADMIN or NETWORK_OPERATOR, matching the backend write restriction.

**Files changed:**

| File | Change |
|------|--------|
| `api-dashboard-tier/react-dashboard/src/app/router.tsx` | Added `NETWORK_MANAGER` to predictions route `allowedRoles` |
| `api-dashboard-tier/react-dashboard/src/lib/constants.ts` | Added `NETWORK_MANAGER` to predictions nav item roles |
| `api-dashboard-tier/react-dashboard/src/pages/PredictionsCenterPage.tsx` | Added `canRunPredictions` guard using `useAuth` |
| `api-dashboard-tier/react-dashboard/src/components/tables/predictions-table.tsx` | Added `canRun` prop; shows "lecture seule" text instead of Relancer button when `false` |

---

## Task 4 — Prometheus Missing from Docker Compose

**Before:** `adapter-ves` (port 7001) and `adapter-netconf` (port 7002) exposed `/metrics` endpoints but Prometheus was not present in `docker-compose.yml`. No metrics were being scraped.

**After:** Prometheus (`prom/prometheus:v2.51.2`) is added to the default Compose stack. It scrapes both adapters every 15 seconds and exposes its UI at `http://localhost:9090`. A Grafana datasource provisioning file auto-registers Prometheus as a Grafana datasource.

**Files changed:**

| File | Change |
|------|--------|
| `infrastructure/docker-compose.yml` | Added `prometheus` service and `prometheus_data` volume |
| `infrastructure/observability/prometheus.yml` | New file — Prometheus scrape config |
| `infrastructure/observability/grafana/provisioning/datasources/prometheus.yml` | New file — Grafana datasource auto-provisioning |

**Verification:**
```bash
# Prometheus ready
curl http://localhost:9090/-/ready
# Targets (adapter-ves and adapter-netconf should show UP)
curl http://localhost:9090/api/v1/targets
```

---

## Task 5 — MLOps Pipeline Disabled State

**Before:** The "Run Offline MLOps Pipeline" button was always enabled in the UI. When `MLOPS_PIPELINE_ENABLED=false` (the default), clicking it triggered a pipeline call that the runner immediately rejected with HTTP 409. There was no proactive signal to the operator that the pipeline was disabled.

**After:** A new endpoint `GET /mlops/pipeline/config` on dashboard-backend reads `MLOPS_PIPELINE_ENABLED` and `MLOPS_PIPELINE_TIMEOUT_SECONDS` and returns them to the UI. The Operations page queries this on load (stale time 60 s) and:
- Shows an amber warning card with the disabled message from the backend.
- Disables the "Run Offline MLOps Pipeline" button and relabels it "Pipeline disabled".

**Files changed:**

| File | Change |
|------|--------|
| `api-dashboard-tier/dashboard-backend/main.py` | Added `GET /mlops/pipeline/config` endpoint |
| `api-dashboard-tier/dashboard-backend/schemas.py` | Added `MlopsPipelineConfigResponse` schema |
| `infrastructure/docker-compose.yml` | Added `MLOPS_PIPELINE_ENABLED`, `MLOPS_PIPELINE_TIMEOUT_SECONDS`, `ROOT_CAUSE_AGENT_URL`, `COPILOT_AGENT_URL` to dashboard-backend environment |
| `api-dashboard-tier/react-dashboard/src/api/mlopsApi.ts` | Added `getMlopsPipelineConfig` function |
| `api-dashboard-tier/react-dashboard/src/pages/mlops/MlopsOperationsPage.tsx` | Added pipeline config query; shows amber notice and disables button when pipeline is disabled |
| `infrastructure/.env.example` | Documents all env vars including `MLOPS_PIPELINE_ENABLED=false` default |
| `infrastructure/.env.demo.example` | Example with `MLOPS_PIPELINE_ENABLED=true` for demo mode |

**Verification:**
```bash
# With MLOPS_PIPELINE_ENABLED=false (default)
curl -H "Authorization: Bearer <token>" http://localhost:8008/api/dashboard/mlops/pipeline/config
# Expected: {"pipeline_enabled": false, "message": "..."}
```

---

## Task 6 — Documentation Updates

READMEs updated to reflect all Scenario B fixes:

| File | Change |
|------|--------|
| `infrastructure/README.md` | Added Prometheus to default service list and published URLs |
| `infrastructure/observability/README.md` | Added Prometheus section before ELK section |
| `api-dashboard-tier/kong-gateway/README.md` | Updated route map to show `/api/dashboard/agentic` → dashboard-backend; documented auth flow |
| `api-dashboard-tier/react-dashboard/README.md` | Updated `/predictions` role list; documented pipeline disabled notice and agentic auth flow |
| `agentic-ai-tier/README.md` | Added "Auth Flow (Scenario B)" section; removed stale note that agentic services bypass auth |

---

## Task 7 — Pre-existing Bug Fix

**`mlops_ops.py` `redact_log` — JWT tokens not marked with `***JWT***`**

The `_REDACTION_PATTERNS` tuple had the generic `token=` pattern running before the JWT-specific pattern. Any JWT appearing after `token=` was replaced with plain `***` before the JWT pattern could produce `***JWT***`. Additionally, the JWT minimum-char requirement (`{8,}`) was too strict for short test tokens. Fixed by:
1. Moving the JWT pattern first in the tuple.
2. Relaxing minimum char counts to `{4,}`, `{2,}`, `{2,}`.
3. Adding `(?!\*\*\*)` negative lookahead to all generic key=value patterns to prevent double-redaction.

This was confirmed pre-existing (failing on the clean baseline commit `bc732b4`).

---

## Validation Results

| Check | Result |
|-------|--------|
| `npm run build` (react-dashboard) | PASS — 0 TypeScript errors |
| `pytest tests/` (dashboard-backend) | PASS — 30/30 passed |
| `docker compose config` | Expected PASS (declarative config only) |
| Pre-existing `LiveStatePage.tsx` number→string errors | FIXED (6 `String()` wraps) |
| Pre-existing `redact_log` JWT test failure | FIXED |

---

## Explicit Exclusions

The following items are intentionally NOT addressed in this fix set:

- Kubernetes / Istio / Helm / KEDA / vLLM — out of scope for Scenario B
- Production TLS / certificate management
- Multi-tenant / multi-region routing
- Prometheus alerting rules or recording rules (scrape config only)
- Grafana dashboards for Prometheus metrics (datasource provisioned; dashboards are operator-defined)
- On-demand prediction re-scoring in BFF mode (returns 422 `SCENARIO_B_LIVE_MODE` by design)
