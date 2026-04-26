# Smart Slice 5G/6G

This repository contains the current NeuroSlice workspace: an end-to-end local 5G/6G network-slicing platform with simulation, ingestion, online AIOps, a dashboard/API stack, observability, agentic assistance services, and an offline MLOps project.

## Repository Layout

- `neuroslice-platform/`: runnable platform code, Docker Compose runtime, service tiers, and the MLOps project
- `report/`: project report assets, including `Rapport_PI_modeling_phase.pdf`

## Current Platform

Implemented tiers:

- `simulation-tier`: Core, Edge, and RAN simulators plus a fault engine
- `ingestion-tier`: VES and NETCONF adapters, normalizer, telemetry exporter, and shared models
- `aiops-tier`: congestion, SLA, and slice-classification workers using promoted ONNX FP16 models when available
- `api-dashboard-tier`: public BFF, auth service, dashboard backend, Kong gateway, and React dashboard
- `agentic-ai-tier`: root-cause and copilot agent services backed by Ollama/LangChain
- `infrastructure`: integrated Docker Compose runtime
- `mlops-tier/batch-orchestrator`: preprocessing, training, MLflow, ONNX export, FP16 conversion, promotion, tests, and reports

Scaffold-only tier:

- `control-tier`

## Runtime Flow

1. Simulators produce Core, Edge, and RAN telemetry.
2. `adapter-ves` and `adapter-netconf` receive raw payloads.
3. `normalizer` writes canonical telemetry to Redis and Kafka.
4. AIOps workers consume `stream:norm.telemetry` and emit congestion, SLA, and slice-classification events.
5. AIOps workers load production models from `models/promoted/{model_name}/current/model_fp16.onnx` and hot reload when `metadata.json` changes.
6. `api-bff-service` exposes KPI, AIOps, SSE, fault/scenario, and feature-view endpoints.
7. `auth-service`, `dashboard-backend`, `kong-gateway`, and `react-dashboard` serve the protected dashboard.
8. `root-cause` and `copilot-agent` provide optional operator-assistance APIs.
9. InfluxDB and Grafana expose telemetry and runtime views.

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

Manual offline training/promotion worker:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops --profile mlops-worker run --rm mlops-worker
```

## Default URLs

- Public API/BFF: `http://localhost:8000`
- Auth/dashboard gateway: `http://localhost:8008`
- React dashboard: `http://localhost:5173`
- VES adapter: `http://localhost:7001`
- NETCONF adapter: `http://localhost:7002`
- Fault engine: `http://localhost:7004`
- Root-cause agent: `http://localhost:7005`
- Copilot agent: `http://localhost:7006`
- Grafana: `http://localhost:3000`
- InfluxDB: `http://localhost:8086`
- MLflow UI: `http://localhost:5000` with `mlops` profile
- MinIO console: `http://localhost:9001` with `mlops` profile
- MLOps API: `http://localhost:8010` with `mlops` profile

Local development admin account:

- email: `admin@neuroslice.tn`
- password: `change-me-now`

Change these defaults before using the stack outside local development.

## Model Deployment Contract

Training exports `model.onnx`, converts it to `model_fp16.onnx`, and promotes selected models into:

```text
models/promoted/{model_name}/{version}/model.onnx
models/promoted/{model_name}/{version}/model_fp16.onnx
models/promoted/{model_name}/current/model_fp16.onnx
models/promoted/{model_name}/current/metadata.json
```

AIOps services mount `mlops-tier/batch-orchestrator/models` as `/mlops/models:ro` and load from the promoted `current/` directory. They poll metadata with `MODEL_POLL_INTERVAL_SEC` and reload ONNX Runtime sessions without container restarts.

## Documentation Map

- Platform overview: `neuroslice-platform/README.md`
- Infrastructure runtime: `neuroslice-platform/infrastructure/README.md`
- Simulation tier: `neuroslice-platform/simulation-tier/README.md`
- Ingestion tier: `neuroslice-platform/ingestion-tier/README.md`
- AIOps tier: `neuroslice-platform/aiops-tier/README.md`
- API and dashboard tier: `neuroslice-platform/api-dashboard-tier/README.md`
- Agentic AI tier: `neuroslice-platform/agentic-ai-tier/README.md`
- MLOps tier: `neuroslice-platform/mlops-tier/README.md`
- Batch orchestrator: `neuroslice-platform/mlops-tier/batch-orchestrator/README.md`

## Contributors

- Ahmed Bouhlel
- Rayen Sebai
- Mouhamed Dhia Chaouachi
- Fourat Hamdi
- Mouhamed Aziz Weslati
- Mouhamed Aziz Boughanmi
