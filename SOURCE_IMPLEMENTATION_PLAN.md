# SOURCE_IMPLEMENTATION_PLAN

Last source inventory update: 2026-04-30
Validation method: source-code inspection only (no runtime execution)

## 1) Current Files / Services Found

### Top-level project areas
- `neuroslice-platform/simulation-tier`
- `neuroslice-platform/ingestion-tier`
- `neuroslice-platform/aiops-tier`
- `neuroslice-platform/control-tier`
- `neuroslice-platform/api-dashboard-tier`
- `neuroslice-platform/mlops-tier`
- `neuroslice-platform/infrastructure`
- `neuroslice-platform/agentic-ai-tier` (implemented but out of current validation scope)

### Scenario B in-scope service code present
- Simulation: `simulator-core`, `simulator-edge`, `simulator-ran`, `fault-engine`
- Ingestion: `adapter-ves`, `adapter-netconf`, `normalizer`, `telemetry-exporter`
- AIOps: `congestion-detector`, `sla-assurance`, `slice-classifier`, `aiops-drift-monitor`
- Control: `alert-management`, `policy-control`
- API/Dashboard: `api-bff-service`, `auth-service`, `dashboard-backend`, `kong-gateway`, `react-dashboard`
- MLOps: `batch-orchestrator`, `mlops-runner`, `mlops-drift-monitor`
- Observability: Prometheus + Grafana provisioning under `infrastructure/observability`

## 2) Existing Endpoints (Source-Defined)

### AIOps services
- `aiops-drift-monitor`: `GET /health`, `GET /drift/latest`, `GET /drift/latest/{model_name}`, `GET /drift/events`, `GET /metrics`
- `congestion-detector`, `sla-assurance`, `slice-classifier`: worker entrypoints (no HTTP endpoints currently)

### Control-tier
- `alert-management`: `GET /health`, `GET /alerts`, `GET /alerts/{alert_id}`, `POST /alerts/{alert_id}/acknowledge`, `POST /alerts/{alert_id}/resolve`
- `policy-control`: `GET /health`, `GET /actions`, `GET /actions/{action_id}`, `POST /actions/{action_id}/approve`, `POST /actions/{action_id}/reject`, `POST /actions/{action_id}/execute`

### API/Dashboard-tier
- `api-bff-service`: `GET /health`, `GET /config`, `GET /api/v1/*` KPI/live/network/aiops/drift/export endpoints, scenario/fault control endpoints
- `dashboard-backend`: health, dashboard/session/prediction/model routes, MLOps routes (overview/models/runs/artifacts/promotions/monitoring/drift/pipeline/orchestration), control proxy routes (`/controls/actions*`, `/controls/drift*`), agentic proxy routes
- `auth-service`: auth + user management endpoints

### MLOps-tier
- `mlops-runner`: `GET /health`, `POST /run-action`
- `mlops-drift-monitor`: `GET /health`, `GET /drift/status`, `GET /drift/events`, `POST /drift/trigger`
- `mlops-api` (`batch-orchestrator/src/api/main.py`): health + prediction endpoints

### Simulation/fault
- `fault-engine`: `GET /health`, `GET /faults/active`, `GET /scenarios`, `POST /scenarios/start`, `POST /scenarios/stop`, `POST /faults/inject`

## 3) Existing Redis Streams / Keys (from source constants and stores)

### Streams
- `stream:raw.ves`
- `stream:raw.netconf`
- `stream:norm.telemetry`
- `stream:fault.events`
- `events.anomaly`
- `events.sla`
- `events.slice.classification`
- `events.drift`
- `stream:control.alerts`
- `stream:control.actions`

### Existing key families
- Entity and simulator state: `entity:{entity_id}`, `faults:active`, `ran:congestion_score`, `core:active_ues`, `core:active_sessions`, `edge:saturation`, `edge:misrouting_ratio`
- AIOps latest-state hashes: `aiops:congestion:{entity_id}`, `aiops:sla:{entity_id}`, `aiops:slice_classification:{entity_id}`, `aiops:drift:{model_name}`
- Control alerts/actions: `control:alerts:*`, `control:actions:*`, `control:alerts:index`, `control:actions:index`, `control:actions:by_alert:{alert_id}`, dedup keys
- MLOps drift monitor state: `drift:last_trigger_ts`, `drift:status`, `drift:events`

## 4) Existing Compose Services (infrastructure/docker-compose.yml)

### Core/default runtime services
- `redis`, `zookeeper`, `kafka`, `influxdb`, `postgres`
- `adapter-ves`, `adapter-netconf`, `normalizer`, `telemetry-exporter`
- `congestion-detector`, `sla-assurance`, `slice-classifier`
- `alert-management`, `policy-control`
- `fault-engine`, `simulator-core`, `simulator-edge`, `simulator-ran`
- `api-bff-service`, `auth-service`, `dashboard-backend`, `kong-gateway`, `react-dashboard`
- `mlops-runner`, `mlops-drift-monitor`
- `prometheus`, `grafana`
- `root-cause`, `copilot-agent` (out of current validation scope)

### Profile-gated services
- `drift` profile: `aiops-drift-monitor`
- `mlops` profile: `mlops-postgres`, `minio`, `minio-init`, `mlflow-server`, `elasticsearch`, `logstash`, `kibana`, `mlops-api`
- `mlops-worker` profile: `mlops-worker`

## 5) Existing Dashboard Routes

### Backend protected routes (dashboard-backend)
- `/dashboard/*`, `/sessions*`, `/predictions*`, `/models`
- `/mlops/*` (overview/models/runs/artifacts/promotions/monitoring/drift/pipeline/orchestration)
- `/controls/actions*`, `/controls/drift*`
- `/agentic/*` (implemented; out of current validation scope)

### Frontend routes (react-dashboard)
- `/dashboard/national`, `/dashboard/region/*`
- `/sessions`, `/live-state`
- `/predictions`
- `/control/actions`
- `/mlops` and child pages (`overview`, `models`, `runs`, `artifacts`, `promotions`, `monitoring`, `drift`, `operations`, `orchestration`)
- `/agentic/root-cause`, `/agentic/copilot`
- `/admin/users`

### Kong routes
- `/api/auth/*`
- `/api/dashboard/*` subsets via service split (`sessions`, `predictions`, `models`, `mlops`, `controls`, `agentic`, `dashboard root`)
- `/api/v1/live*` to `api-bff-service`

## 6) Existing Metrics Endpoints / Observability Wiring

### Scenario B metrics endpoints now present
- AIOps workers:
  - `congestion-detector`: `:9101/metrics`
  - `sla-assurance`: `:9102/metrics`
  - `slice-classifier`: `:9103/metrics`
- AIOps drift/evaluation:
  - `aiops-drift-monitor`: `GET /metrics` (profile `drift`)
  - `online-evaluator`: `GET /metrics`
- Control:
  - `alert-management`: `GET /metrics`
  - `policy-control`: `GET /metrics`
- Dashboard/API:
  - `dashboard-backend`: `GET /metrics`
  - `api-bff-service`: `GET /metrics`
- MLOps:
  - `mlops-runner`: `GET /metrics`
  - `mlops-drift-monitor`: `GET /metrics`

### Prometheus scrape jobs now include
- `adapter-ves`, `adapter-netconf`
- `congestion-detector`, `sla-assurance`, `slice-classifier`
- `online-evaluator`
- `alert-management`, `policy-control`
- `dashboard-backend`, `api-bff-service`
- `mlops-runner`, `mlops-drift-monitor`
- optional `aiops-drift-monitor` (drift profile)
- `prometheus` self-scrape

### Grafana provisioning now includes dedicated dashboards
- `neuroslice-aiops-dashboard.json`
- `neuroslice-control-dashboard.json`
- `neuroslice-mlops-dashboard.json`
- `neuroslice-platform-overview.json`

## 7) Current Gap Status

### Phase 1: Observability full coverage
- Closed in source: metrics endpoints, Prometheus scrapes, and Grafana dashboard provisioning are wired for the required Scenario B services.

### Phase 2: Simulated closed-loop control
- Closed in source:
  - `policy-control` uses `simulation_actuator.py`
  - actuations are persisted and streamed (`stream:control.actuations`)
  - simulators consume `control:sim:*` keys
  - APIs exposed at `/actuations` and dashboard proxy `/controls/actuations*`

### Phase 3: Dashboard runtime control
- Closed in source:
  - Redis runtime contract `runtime:service:{service_name}:*`
  - AIOps workers gate processing when disabled
  - `mlops-drift-monitor` gates trigger behavior when disabled
  - dashboard-backend routes `/runtime/services*` with role checks
  - Kong route `/api/dashboard/runtime*`
  - React runtime controls integrated in `/mlops/orchestration`

### Phase 4: Online model evaluation
- Closed in source:
  - new `aiops-tier/online-evaluator`
  - stream/key contracts: `events.evaluation`, `aiops:evaluation:{model_name}`
  - BFF routes `/api/v1/evaluation/*`
  - dashboard routes `/mlops/evaluation*`
  - React monitoring panel under `/mlops/monitoring`
  - Prometheus evaluation metrics added
  - Compose service `online-evaluator` added to default runtime

### Phase 5: Source-level E2E tests
- Closed in source: `neuroslice-platform/tests/e2e_source/` added with compose/streams/mlops/routes/docs contract tests.

### Phase 6: Runbook coverage
- Closed in source: `RUNBOOK/` refreshed for runtime flags, simulated actuation, observability coverage, and evaluation flow.

### Phase 7: completion report
- Closed in source: `IMPLEMENTATION_COMPLETION_REPORT.md` created and populated.

## 8) Files Modified for Remaining Work

### Runtime/Control
- `neuroslice-platform/control-tier/policy-control/app/simulation_actuator.py`
- `neuroslice-platform/control-tier/policy-control/app/{action_store.py,main.py,schemas.py}`
- `neuroslice-platform/simulation-tier/{simulator-edge,simulator-ran}/engine.py`
- `neuroslice-platform/api-dashboard-tier/dashboard-backend/main.py`
- `neuroslice-platform/api-dashboard-tier/react-dashboard/src/{api/controlApi.ts,pages/ControlActionsPage.tsx}`

### Runtime flags + observability
- `neuroslice-platform/aiops-tier/shared/runtime_control.py`
- `neuroslice-platform/aiops-tier/{congestion-detector,sla-assurance,slice-classifier}/consumer.py`
- `neuroslice-platform/aiops-tier/drift-monitor/app/{config.py,consumer.py}`
- `neuroslice-platform/mlops-tier/drift-monitor/main.py`
- `neuroslice-platform/api-dashboard-tier/kong-gateway/kong.yml`
- `neuroslice-platform/api-dashboard-tier/react-dashboard/src/{api/runtimeApi.ts,pages/mlops/MlopsOrchestrationPage.tsx}`
- `neuroslice-platform/infrastructure/observability/prometheus.yml`
- `neuroslice-platform/infrastructure/observability/grafana/dashboards/*.json`

### Online evaluator
- `neuroslice-platform/aiops-tier/online-evaluator/{Dockerfile,requirements.txt,main.py}`
- `neuroslice-platform/infrastructure/docker-compose.yml`
- `neuroslice-platform/api-dashboard-tier/api-bff-service/main.py`
- `neuroslice-platform/api-dashboard-tier/dashboard-backend/main.py`
- `neuroslice-platform/api-dashboard-tier/react-dashboard/src/{api/mlopsApi.ts,pages/mlops/MlopsMonitoringPage.tsx}`

### Source tests + docs
- `neuroslice-platform/tests/e2e_source/*.py`
- README/runbook updates across infrastructure, observability, aiops, mlops, control, simulation, dashboard tiers

## 9) Scope Guardrails for This Implementation
- Do not implement `misrouting-detector`.
- Do not implement production Kubernetes/Istio or real PCF/NMS integrations.
- Do not expose Docker socket or arbitrary command execution to dashboard/browser.
- Keep control-loop actuation simulated via Redis keys/streams only.
- Keep agentic tier untouched except scope notes in documentation where necessary.
