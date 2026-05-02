# 10 Troubleshooting

## Port conflicts
Symptoms:
- services fail to start

Actions:
- check occupied host ports (`7001`, `7002`, `7004`, `8000`, `8008`, `5173`, etc.)
- remap ports via environment overrides if needed

## PostgreSQL issues
Symptoms:
- auth/dashboard startup failures
- migration or credential errors

Actions:
- verify `DATABASE_URL` and init credentials in Compose
- if old volume has stale roles, recreate volumes:
  - `docker compose down -v`
  - `docker compose up --build`

## Login failures
Symptoms:
- `/api/auth/*` unauthorized unexpectedly

Actions:
- verify `DASHBOARD_JWT_SECRET` consistency
- verify seeded admin user exists
- ensure browser calls go through Kong (`:8008`), not internal service ports

## Missing dashboard data
Symptoms:
- empty sessions/predictions/live views

Actions:
- confirm simulators + ingestion + normalizer are running
- verify Redis streams/hashes are populated
- verify `DASHBOARD_DATA_PROVIDER=bff`

## Fallback mode active
Symptoms:
- prediction details show fallback behavior

Actions:
- verify promoted ONNX artifacts exist in `models/promoted/{model}/current/`
- verify `/mlops/models` mount is present and read-only in worker containers

## Missing promoted models
Symptoms:
- model load warnings in AIOps logs

Actions:
- run offline pipeline/promotion path
- verify `model_fp16.onnx` and `metadata.json` under each `current/` directory

## Drift reference missing
Symptoms:
- `aiops-drift-monitor` reports `reference_missing`

Actions:
- regenerate drift references from MLOps project
- verify `drift_reference.npz` and `drift_feature_schema.json` in promoted current dirs

## Kong routing issues
Symptoms:
- 404/502 on dashboard APIs

Actions:
- verify Kong declarative config (`kong.yml`)
- verify target services (`auth-service`, `dashboard-backend`) are healthy

## Redis empty streams
Symptoms:
- no telemetry/anomaly/control events

Actions:
- check simulator -> adapter path
- check adapter publish logic
- verify normalizer consumer groups and stream names

## InfluxDB no data
Symptoms:
- telemetry charts empty

Actions:
- verify `telemetry-exporter` consumption from Kafka `telemetry-norm`
- verify InfluxDB URL/token/org/bucket envs
