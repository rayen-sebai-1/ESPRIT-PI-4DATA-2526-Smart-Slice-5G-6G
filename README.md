# Smart Slice 5G/6G

This repository contains the NeuroSlice platform: a local, multi-service 5G/6G network-slicing environment for simulation, telemetry ingestion, online AIOps inference, dashboard access, observability, and offline MLOps workflows.

## Repository Layout

- `neuroslice-platform/`: runnable platform code, Docker Compose stack, dashboards, simulators, and MLOps project
- `report/`: project report assets, including `Rapport_PI_modeling_phase.pdf`

## What Runs Today

The current implementation covers this end-to-end path:

1. Simulators generate Core, Edge, and RAN telemetry.
2. VES and NETCONF adapters receive the payloads.
3. The normalizer writes canonical events to Redis and Kafka.
4. Runtime AIOps workers score congestion, SLA risk, and slice classification.
5. The public API/BFF exposes live KPIs, AIOps outputs, and fault/scenario controls.
6. The protected dashboard stack exposes authentication, Kong routing, and the React UI.
7. Grafana and InfluxDB provide observability for telemetry and runtime AIOps outputs.

## Quick Start

```bash
cd neuroslice-platform/infrastructure
cp .env.example .env
docker compose up --build
```

Optional integrated MLOps profile:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops up --build
```

## Default URLs

- Public API/BFF: `http://localhost:8000`
- React dashboard: `http://localhost:5173`
- Kong gateway: `http://localhost:8008`
- Fault engine: `http://localhost:7004`
- Grafana: `http://localhost:3000`
- InfluxDB: `http://localhost:8086`
- MLflow UI: `http://localhost:5000` (`mlops` profile)
- MLOps API: `http://localhost:8010` (`mlops` profile)

Development dashboard bootstrap in the current Compose file seeds an admin account by default:

- email: `admin@neuroslice.tn`
- password: `change-me-now`

Change those defaults before using the stack outside local development.

## Current Status

Implemented tiers:

- `simulation-tier`
- `ingestion-tier`
- `aiops-tier`
- `api-dashboard-tier`
- `infrastructure`
- `mlops-tier/batch-orchestrator`

Present but still placeholder-only:

- `control-tier`
- `agentic-ai-tier`

Deferred in this iteration:

- `aiops-tier/misrouting-detector`
- Kubernetes and Istio deployment assets

## Documentation Map

- Platform overview: `neuroslice-platform/README.md`
- Infrastructure and Compose runtime: `neuroslice-platform/infrastructure/README.md`
- Simulation tier: `neuroslice-platform/simulation-tier/README.md`
- Ingestion tier: `neuroslice-platform/ingestion-tier/README.md`
- AIOps tier: `neuroslice-platform/aiops-tier/README.md`
- API and dashboard tier: `neuroslice-platform/api-dashboard-tier/README.md`
- MLOps tier: `neuroslice-platform/mlops-tier/README.md`
- Batch orchestrator project: `neuroslice-platform/mlops-tier/batch-orchestrator/README.md`

## Contributors

- Ahmed Bouhlel
- Rayen Sebai
- Mouhamed Dhia Chaouachi
- Fourat Hamdi
- Mouhamed Aziz Weslati
- Mouhamed Aziz Boughanmi
