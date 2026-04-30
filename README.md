# Smart Slice 5G/6G

Last verified: 2026-04-30.

This repository contains the current NeuroSlice workspace: an end-to-end local 5G/6G network-slicing platform with simulation, ingestion, online AIOps, a dashboard/API stack, observability, agentic assistance services, and an offline MLOps project.

## Scenario B Validation Scope (Current)

- Active validation target: Docker Compose local PoC (`neuroslice-platform/infrastructure/docker-compose.yml`)
- Explicitly out of scope in the current validation cycle: `agentic-ai-tier`
- Explicitly deferred/future in current validation cycle: `misrouting-detector`
- Agentic AI tier is implemented but excluded from current Scenario B validation scope.

## Repository Layout

- `neuroslice-platform/`: runnable platform code, Docker Compose runtime, service tiers, and the MLOps project
- `report/`: project report assets, including `Rapport_PI_modeling_phase.pdf`

## Current Platform

Implemented tiers:

- `simulation-tier`: Core, Edge, and RAN simulators plus a fault engine
- `ingestion-tier`: VES and NETCONF adapters, normalizer, telemetry exporter, and shared models
- `aiops-tier`: congestion, SLA, and slice-classification workers, plus optional Scenario B `aiops-drift-monitor` using Alibi Detect MMD
- `api-dashboard-tier`: public BFF (with Redis Live State endpoints), auth service, dashboard backend, Kong gateway, and React dashboard
- `agentic-ai-tier`: root-cause and copilot agent services backed by Ollama/LangChain
- `control-tier`: deterministic alert management and policy-control services with human-in-the-loop lifecycle and Redis-simulated actuation
- `infrastructure`: integrated Docker Compose runtime
- `mlops-tier/batch-orchestrator`: preprocessing, training, MLflow, ONNX export, FP16 conversion, promotion, tests, and reports

## Runtime Flow

1. Simulators produce Core, Edge, and RAN telemetry.
2. `adapter-ves` and `adapter-netconf` receive raw payloads and publish to `stream:raw.ves` and `stream:raw.netconf`.
3. `normalizer` writes canonical telemetry to `stream:norm.telemetry`, Redis entity state (`entity:{entity_id}`), and Kafka topic `telemetry-norm`.
4. AIOps workers consume `stream:norm.telemetry` and emit congestion, SLA, and slice-classification events.
5. Default `mlops-drift-monitor` watches anomaly bursts on `events.anomaly` and can trigger the offline MLOps pipeline through `mlops-runner`.
6. Optional `aiops-drift-monitor` (profile `drift`) consumes `stream:norm.telemetry`, publishes `events.drift`, and stores latest drift state under `aiops:drift:*`.
7. `online-evaluator` computes rolling runtime metrics (accuracy/precision/recall/F1) from prediction streams and Scenario B pseudo-ground-truth and publishes `events.evaluation`.
8. AIOps workers load production models from `models/promoted/{model_name}/current/model_fp16.onnx` and hot reload when `metadata.json` changes.
9. `api-bff-service` exposes KPI, AIOps, Live State, SSE, fault/scenario, network insights, feature-view, drift-status, and evaluation endpoints.
10. `auth-service`, `dashboard-backend`, `kong-gateway`, and `react-dashboard` serve the protected dashboard, including runtime service flag controls.
11. `root-cause` and `copilot-agent` provide optional operator-assistance APIs.
12. `alert-management` normalizes AIOps events into lifecycle-managed alerts.
13. `policy-control` converts unresolved alerts into operator-approved remediation recommendations and applies simulated Redis actuations.
14. InfluxDB, Prometheus, and Grafana expose telemetry and runtime views.

## Quick Start

```bash
cd neuroslice-platform/infrastructure
docker compose up --build
```

Optional integrated MLOps services:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops up --build
```

Optional drift detection:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile drift up --build
```

Manual offline training/promotion worker:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops --profile mlops-worker run --rm mlops-worker
```

## Default URLs

- Public API/BFF: `http://localhost:8000`
- Auth/dashboard gateway: `http://localhost:8008`
- React dashboard: `http://localhost:5173`
- React live-state overview: `http://localhost:5173/live-state`
- VES adapter: `http://localhost:7001`
- NETCONF adapter: `http://localhost:7002`
- Fault engine: `http://localhost:7004`
- Root-cause agent: `http://localhost:7005`
- Copilot agent: `http://localhost:7006`
- Alert management: `http://localhost:7010`
- Policy control: `http://localhost:7011`
- aiops-drift-monitor API/metrics: `http://localhost:7012` with `drift` profile
- mlops-drift-monitor: internal-only service (`mlops-drift-monitor:8030` on the Compose network; no host-published port)
- Grafana: `http://localhost:3000`
- InfluxDB: `http://localhost:8086`
- MLflow UI: `http://localhost:5000` with `mlops` profile
- MinIO API: `http://localhost:9000` with `mlops` profile
- MinIO console: `http://localhost:9001` with `mlops` profile
- MLOps API: `http://localhost:8010` with `mlops` profile
- Elasticsearch: `http://localhost:9200` with `mlops` profile
- Kibana: `http://localhost:5601` with `mlops` profile

Local development admin account:

- email: `admin@neuroslice.tn`
- password: `change-me-now`

Change these defaults before using the stack outside local development.

## Model Deployment Contract

Training exports `model.onnx`, converts it to `model_fp16.onnx`, and promotes selected models into:

```text
models/promoted/{model_name}/{version}/model.onnx
models/promoted/{model_name}/{version}/model_fp16.onnx
models/promoted/{model_name}/current/model.onnx
models/promoted/{model_name}/current/model_fp16.onnx
models/promoted/{model_name}/current/metadata.json
models/promoted/{model_name}/current/version.txt
models/promoted/{model_name}/current/drift_reference.npz
models/promoted/{model_name}/current/drift_feature_schema.json
```

AIOps services mount `mlops-tier/batch-orchestrator/models` as `/mlops/models:ro` and load from the promoted `current/` directory. They poll metadata with `MODEL_POLL_INTERVAL_SEC` and reload ONNX Runtime sessions without container restarts.

## Documentation Map

- Platform overview: `neuroslice-platform/README.md`
- Infrastructure runtime: `neuroslice-platform/infrastructure/README.md`
- Simulation tier: `neuroslice-platform/simulation-tier/README.md`
- Ingestion tier: `neuroslice-platform/ingestion-tier/README.md`
- AIOps tier: `neuroslice-platform/aiops-tier/README.md`
- API and dashboard tier: `neuroslice-platform/api-dashboard-tier/README.md`
- Control tier: `neuroslice-platform/control-tier/README.md`
- Agentic AI tier: `neuroslice-platform/agentic-ai-tier/README.md`
- MLOps tier: `neuroslice-platform/mlops-tier/README.md`
- Batch orchestrator: `neuroslice-platform/mlops-tier/batch-orchestrator/README.md`
- Observability: `neuroslice-platform/infrastructure/observability/README.md`
- Scenario B drift design: `neuroslice-platform/SCENARIO_B_DRIFT_DETECTION.md`

## Runbook

- Scenario B runbook folder: `RUNBOOK/`
- Start here: `RUNBOOK/00_OVERVIEW.md`

## Contributors

- Ahmed Bouhlel
- Rayen Sebai
- Mouhamed Dhia Chaouachi
- Fourat Hamdi
- Mouhamed Aziz Weslati
- Mouhamed Aziz Boughanmi
