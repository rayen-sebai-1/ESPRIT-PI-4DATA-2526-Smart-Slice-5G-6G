# Infrastructure Layer

Runtime orchestration, platform dependencies, and observability assets for NeuroSlice.

## Purpose

This layer wires all tiers together using Docker Compose and provides shared runtime services:

- Redis (state + streams)
- Kafka + Zookeeper (event bus)
- InfluxDB (time-series persistence)
- Grafana (dashboards)

It also contains deployment scaffolds for future Kubernetes and Istio environments.

## Main Files

- `docker-compose.yml`: full multi-service topology.
- `.env.example`: environment and port template.
- `.env`: local runtime configuration.
- `observability/`: Grafana provisioning + Flux examples.
- `k8s/`: Kubernetes deployment scaffold.
- `istio/`: service-mesh scaffold.

## Service Topology (Compose)

Infrastructure services:

- `redis`
- `zookeeper`
- `kafka`
- `influxdb`
- `grafana`

Application services orchestrated here:

- Simulation tier (`simulator-core`, `simulator-edge`, `simulator-ran`, `fault-engine`)
- Ingestion tier (`adapter-ves`, `adapter-netconf`, `normalizer`, `telemetry-exporter`)
- AIOps tier (`congestion-detector`, `slice-classifier`, `sla-assurance`)
- API/dashboard tier (`api-bff-service`, `auth-service`, `dashboard-backend`, `kong-gateway`, `react-dashboard`)

## Quick Start

```bash
cd neuroslice-platform/infrastructure
cp .env.example .env
docker compose up --build
```

Useful URLs (default ports):

- NeuroSlice API BFF: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Dashboard frontend: `http://localhost:5173`
- Dashboard gateway (Kong): `http://localhost:8008`
- Protected dashboard API via Kong: `http://localhost:8008/api/auth/*` and `http://localhost:8008/api/dashboard/*`
- Grafana: `http://localhost:3000`
- InfluxDB: `http://localhost:8086`

## Environment Variables

Primary knobs in `.env`:

- Site and simulation speed: `SITE_ID`, `TICK_INTERVAL_SEC`, `SIM_SPEED`
- Core ports: `REDIS_PORT`, `API_PORT`, `VES_PORT`, `NETCONF_PORT`, `FAULT_ENGINE_PORT`
- AIOps thresholds: `CONGESTION_THRESHOLD`, `SLICE_MISMATCH_CONFIDENCE_THRESHOLD`, `SLA_RISK_THRESHOLD`
- Dashboard ports/secrets: `DASHBOARD_FRONTEND_PORT`, `DASHBOARD_KONG_PORT`, `DASHBOARD_JWT_SECRET`
- Grafana auth: `GRAFANA_USER`, `GRAFANA_PASSWORD`

Dashboard notes:

- `auth-service` and `dashboard-backend` are internal-only Compose services exposed to the browser through `kong-gateway`.
- `react-dashboard` proxies `/api/*` to `kong-gateway`, making Kong the single public dashboard entry point in Scenario B.
- `react-dashboard/` contains the full frontend project; there is no parallel `dashboard-frontend/` runtime folder.
- `kong-gateway/` is the only gateway folder; there is no parallel `kong/` runtime folder.

## Observability Assets

- Grafana data source provisioning:
- `observability/grafana/provisioning/datasources/`

- Grafana dashboards:
- `observability/grafana/provisioning/dashboards/`

- Example Flux query:
- `observability/query.flux`

## Notes for Future Deployment

- `k8s/` and `istio/` are placeholders for production-grade orchestration and service mesh policies.
- Compose is currently the authoritative local integration environment.
