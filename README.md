# Smart Slice Selection in 5G/6G

This repository contains the `neuroslice-platform`, a Scenario B Docker Compose proof-of-concept for end-to-end telecom simulation, ingestion, live AIOps runtime inference, API access, and observability.

## Implemented runtime path (Scenario B)

The live path is now:

1. Simulators emit telemetry (Core/Edge/RAN).
2. VES/NETCONF adapters ingest events.
3. Normalizer builds canonical telemetry (`stream:norm.telemetry`, `telemetry-norm`).
4. Runtime AIOps services consume normalized telemetry:
   - `aiops-tier/congestion-detector`
   - `aiops-tier/slice-classifier`
   - `aiops-tier/sla-assurance`
5. Runtime inference outputs are published to platform streams/topics:
   - `events.anomaly`
   - `events.slice.classification`
   - `events.sla`
6. Latest AIOps state is stored in Redis (`aiops:*` keys) and exposed via API/BFF.

## Quick start

```bash
cd neuroslice-platform/infrastructure
cp .env.example .env
docker compose up --build
```

Core checks:

```bash
curl http://localhost:8000/health
curl "http://localhost:8000/api/v1/aiops/congestion/latest?limit=20"
curl "http://localhost:8000/api/v1/aiops/sla/latest?limit=20"
curl "http://localhost:8000/api/v1/aiops/slice-classification/latest?limit=20"
```

## Documentation

- Full platform README: `neuroslice-platform/README.md`
- Simulation details: `neuroslice-platform/simulation-tier/README.md`
- MLOps batch orchestrator: `neuroslice-platform/mlops-tier/batch-orchestrator/`

## Intentionally out of scope in this iteration

- `aiops-tier/misrouting-detector`
- Kubernetes deployment (`infrastructure/k8s`)
- Istio/service mesh (`infrastructure/istio`)
- Pending tiers/services: `agentic-ai-tier`, `control-tier`, `api-dashboard-tier/auth-service`, `api-dashboard-tier/kong-gateway`, `api-dashboard-tier/react-dashboard`

## Contributors

- Ahmed Bouhlel
- Rayen Sebai
- Mouhamed Dhia Chaouachi
- Fourat Hamdi
- Mouhamed Aziz Weslati
- Mouhamed Aziz Boughanmi
