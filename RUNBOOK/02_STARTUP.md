# 02 Startup

## Default platform runtime
From `neuroslice-platform/infrastructure/`:

```bash
docker compose up --build
```

This starts core platform services, including:
- simulation-tier services
- ingestion-tier services
- AIOps workers (`congestion-detector`, `sla-assurance`, `slice-classifier`)
- control-tier services
- dashboard/API stack
- `mlops-runner` (internal only)
- `mlops-drift-monitor` (internal only)

## Runtime with integrated MLOps profile
```bash
docker compose --profile mlops up --build
```

Adds:
- `mlops-postgres`
- `minio`, `minio-init`
- `mlflow-server`
- `elasticsearch`, `logstash`, `kibana`
- `mlops-api`

## Runtime with Alibi drift profile
```bash
docker compose --profile drift up --build
```

Adds optional AIOps statistical drift service:
- `aiops-drift-monitor` (Alibi Detect MMD)

## Combined profiles
```bash
docker compose --profile mlops --profile drift up --build
```

## Manual offline worker run
```bash
docker compose --profile mlops --profile mlops-worker run --rm mlops-worker
```

## Expected URLs after startup
- BFF: `http://localhost:8000`
- Kong: `http://localhost:8008`
- Dashboard: `http://localhost:5173`
- VES: `http://localhost:7001`
- NETCONF: `http://localhost:7002`
- Fault engine: `http://localhost:7004`
- Control services: `7010`, `7011`
- Drift profile API/metrics: `http://localhost:7012`
- Observability: Prometheus `9090`, Grafana `3000`, InfluxDB `8086`
- Optional `mlops`: MLflow `5000`, MinIO `9001`, Kibana `5601`, MLOps API `8010`

## Notes
- `dashboard-backend` default provider in Compose is `bff`.
- `mlops-runner` is not host-published; only internal services call it.
- Alibi drift (`aiops-drift-monitor`) requires the `drift` profile.
