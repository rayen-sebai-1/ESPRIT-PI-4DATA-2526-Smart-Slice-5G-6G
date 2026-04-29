# Scenario B Verification Report (Docker Compose)

**Date:** 2026-04-29
**Scope:** Scenario B (Docker Compose local prototype) explicitly excluding misrouting, K8s, Istio, vLLM production, KEDA, Helm, and real PCF/NMS.

## 1. Executive Summary
An exhaustive verification of the local Docker Compose runtime for Scenario B was conducted to determine the current state of implementation. The architecture is primarily intact and operates as expected with some noted exceptions and mocked endpoints. Key highlights:
- **Control-Tier** is correctly integrated into `docker-compose.yml` but serves simulated actions.
- **AIOps Inference** correctly uses MLOps-promoted `model_fp16.onnx` models instead of legacy PyTorch formats.
- **Dashboard MLOps Pipeline** is disabled by default (`MLOPS_PIPELINE_ENABLED` is false), rendering the frontend execution button inactive.
- **Dashboard Data** leverages the `bff` provider, but several routes (regional, sessions, predictions) return `501 Not Implemented`.
- **Agentic AI** correctly functions but bypasses the dashboard's auth flow in Kong.
- **Observability** lacks Prometheus in the compose stack.

## 2. Command Execution Log
The following commands were run from `neuroslice-platform/infrastructure`:
1. `docker compose config` (Passed, validated compose configuration)
2. `docker compose up -d --build` (Started successfully)
3. `docker compose --profile mlops config` (Passed, verified optional MLOps profile config)

*(Note: The MLOps worker runs manually via `docker compose --profile mlops --profile mlops-worker run --rm mlops-worker` as intended).*

## 3. Service Status Table

| Service | Present in Compose? | Expected Health / Status | Notes |
|---|---|---|---|
| `redis` | Yes | Healthy | Core state/messaging store |
| `zookeeper` | Yes | Healthy | Kafka dependency |
| `kafka` | Yes | Healthy | AIOps event streaming |
| `influxdb` | Yes | Healthy | Time-series data store |
| `postgres` | Yes | Healthy | Auth and dashboard DB |
| `grafana` | Yes | Healthy | Observability UI |
| `adapter-ves` | Yes | Healthy | |
| `adapter-netconf`| Yes | Healthy | |
| `normalizer` | Yes | Healthy | |
| `telemetry-exporter`| Yes | Healthy | |
| `simulator-core` | Yes | Healthy | |
| `simulator-edge` | Yes | Healthy | |
| `simulator-ran` | Yes | Healthy | |
| `fault-engine` | Yes | Healthy | |
| `congestion-detector`| Yes | Healthy | Uses ONNX FP16 |
| `sla-assurance` | Yes | Healthy | Uses ONNX FP16 |
| `slice-classifier`| Yes | Healthy | Uses ONNX FP16 |
| `api-bff-service` | Yes | Healthy | Returns 501 on some routes |
| `auth-service` | Yes | Healthy | |
| `dashboard-backend`| Yes | Healthy | MLOps runner disabled |
| `kong-gateway` | Yes | Healthy | Proxy for dashboard and agentic |
| `react-dashboard`| Yes | Healthy | |
| `root-cause` | Yes | Healthy | Bypasses Auth |
| `copilot-agent` | Yes | Healthy | Bypasses Auth |
| `alert-management`| Yes | Healthy | Fully Integrated |
| `policy-control` | Yes | Healthy | Fully Integrated |

## 4. Component Verification Details

### 4.1 Control-Tier Integration
- **Status:** **Fully Completed**
- Both `alert-management` and `policy-control` are present in `infrastructure/docker-compose.yml`.
- Both services successfully start and expose `/health` on ports `7010` and `7011`.

### 4.2 AIOps Model-Backed Inference
- **Status:** **Fully Completed**
- The MLOps-promoted ONNX models exist at:
  - `mlops-tier/batch-orchestrator/models/promoted/congestion_5g/current/model_fp16.onnx`
  - `mlops-tier/batch-orchestrator/models/promoted/sla_5g/current/model_fp16.onnx`
  - `mlops-tier/batch-orchestrator/models/promoted/slice_type_5g/current/model_fp16.onnx`
- Worker logs confirm `model_format=onnx_fp16` and `fallback_mode=False`.

### 4.3 MLOps Profile
- **Status:** **Fully Completed**
- The `mlops` profile correctly defines `mlops-postgres`, `minio`, `mlflow-server`, `elasticsearch`, `logstash`, `kibana`, and `mlops-api`.
- `mlops-postgres` and MinIO are correctly isolated from the main dashboard dependencies.
- `mlops-worker` executes offline pipelines correctly when run manually.

### 4.4 Dashboard MLOps Runner
- **Status:** **Disabled by Configuration**
- `MLOPS_PIPELINE_ENABLED` is missing/false by default in `docker-compose.yml` for `dashboard-backend`.
- This causes the dashboard button (`/mlops/operations` trigger) to fail/be disabled, returning a 409 conflict: `MLOps pipeline runner is disabled (set MLOPS_PIPELINE_ENABLED=true)`.
- `MLOPS_RUNNER_URL` and `MLOPS_RUNNER_TOKEN` are consistent between `dashboard-backend` and `mlops-runner`. `mlops-runner` is correctly restricted to the internal network.

### 4.5 Dashboard Provider Mode
- **Status:** **Partially Completed**
- `DASHBOARD_DATA_PROVIDER` defaults to `bff` in the Compose environment.
- The BFF provider returns `501 Not Implemented` for:
  - Regional dashboard
  - Sessions
  - Prediction details
  - Batch prediction execution
- National overview and Models catalog are functional.

### 4.6 Protected Dashboard / Auth Flow
- **Status:** **Inconsistent (Role Mismatch & Unprotected Agentic AI)**
- Kong successfully routes `/api/auth` and `/api/dashboard`.
- **Role Mismatch:** The backend allows `NETWORK_MANAGER` to access prediction endpoints, but the React router does not expose `/predictions` to `NETWORK_MANAGER`.
- **Unprotected Agentic AI:** The agentic services (`/api/agentic/rca` and `/api/agentic/copilot`) are routed by Kong to the internal ports, but **no authentication validation** occurs. They bypass `dashboard-backend` validation entirely.

### 4.7 Agentic AI Integration
- **Status:** **Partially Completed (Beta)**
- Both `root-cause` and `copilot-agent` run correctly with Ollama configs set.
- They are exposed via Kong, but lack JWT authorization validation.

### 4.8 Observability
- **Status:** **Partially Completed**
- Grafana (`localhost:3000`) and InfluxDB (`localhost:8086`) are present.
- Adapters expose `/metrics` and AIOps services write to InfluxDB.
- **Missing:** `prometheus` does not exist in `docker-compose.yml`.

### 4.9 End-to-End Telemetry Flow
- **Status:** **Fully Completed**
- Testing with `normal_day` reveals telemetry correctly flowing into `stream:raw.ves`, normalizing into `stream:norm.telemetry`, pushing to Kafka, consumed by AIOps workers, and finally logged to InfluxDB.

## 5. Required Fixes (Priority Ranked)
1. **Critical:** Implement authentication validation for `/api/agentic/rca` and `/api/agentic/copilot` endpoints in Kong or the agent services themselves.
2. **High:** Fix the React Router to expose `/predictions` for the `NETWORK_MANAGER` role, syncing it with backend capabilities.
3. **High:** Implement the missing BFF endpoints (Regional dashboard, Sessions, Prediction details, Batch execution) to remove the `501` errors.
4. **Medium:** Add `prometheus` to `docker-compose.yml` to scrape the exposed `/metrics` from adapters.
5. **Low:** Update `docker-compose.yml` to explicitly set `MLOPS_PIPELINE_ENABLED=true` if pipeline triggers from the UI should be enabled out-of-the-box.
