# Smart Slice 5G/6G

This repository contains the current NeuroSlice workspace: an end-to-end local 5G/6G network-slicing platform with simulation, telemetry ingestion, runtime AIOps, a protected dashboard stack, observability, and an offline MLOps project.

## Repository Layout

- `neuroslice-platform/`: runnable platform code, Docker Compose runtime, dashboard services, simulators, and the MLOps project
- `report/`: project report assets, including `Rapport_PI_modeling_phase.pdf`

## What Runs Today

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

Current runtime flow:

1. Core, Edge, and RAN simulators generate synthetic telemetry.
2. `adapter-ves` and `adapter-netconf` accept the payloads.
3. `normalizer` converts them into the shared canonical event model and stores latest entity state in Redis.
4. Runtime AIOps workers score congestion, SLA risk, and slice classification.
5. `api-bff-service` exposes public KPI, AIOps, SSE, and fault/scenario endpoints.
6. `auth-service`, `dashboard-backend`, `kong-gateway`, and `react-dashboard` serve the protected dashboard experience.
7. InfluxDB and Grafana expose telemetry and runtime monitoring views.

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
- VES adapter: `http://localhost:7001`
- NETCONF adapter: `http://localhost:7002`
- Fault engine: `http://localhost:7004`
- React dashboard: `http://localhost:5173`
- Kong gateway: `http://localhost:8008`
- Grafana: `http://localhost:3000`
- InfluxDB: `http://localhost:8086`
- MLflow UI: `http://localhost:5000` (`mlops` profile)
- MLOps API: `http://localhost:8010` (`mlops` profile)

The current Compose file seeds an admin account for local development:

- email: `admin@neuroslice.tn`
- password: `change-me-now`

Replace that default before using the stack outside local development.

## Current Notes

- `control-tier` and `agentic-ai-tier` do not contain active services yet.
- Runtime AIOps services read local artifacts from `mlops-tier/batch-orchestrator`, but the repository does not ship promoted runtime models by default.
- The tracked `models/registry.json` exists, but it currently contains no promoted entries, so fallback and heuristic loading still matter.

## Documentation Map

- Platform overview: `neuroslice-platform/README.md`
- Infrastructure runtime: `neuroslice-platform/infrastructure/README.md`
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
