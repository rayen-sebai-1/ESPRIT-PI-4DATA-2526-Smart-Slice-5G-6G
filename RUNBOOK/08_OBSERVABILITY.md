# 08 Observability

## Components
- Prometheus (`9090`)
- Grafana (`3000`)
- InfluxDB (`8086`)
- Optional ELK stack via `mlops` profile (`elasticsearch`, `logstash`, `kibana`)

## Prometheus
Current source config (`infrastructure/observability/prometheus.yml`) scrapes:
- `adapter-ves`
- `adapter-netconf`
- `congestion-detector`
- `sla-assurance`
- `slice-classifier`
- `online-evaluator`
- `alert-management`
- `policy-control`
- `dashboard-backend`
- `api-bff-service`
- `mlops-runner`
- `mlops-drift-monitor`
- optional `aiops-drift-monitor` (`drift` profile)
- Prometheus self

## Grafana
Provisioning assets exist under:
- `infrastructure/observability/grafana/provisioning/datasources/`
- `infrastructure/observability/grafana/provisioning/dashboards/`
- `infrastructure/observability/grafana/dashboards/`

Provisioned dashboards:
- `neuroslice-platform-overview.json`
- `neuroslice-aiops-dashboard.json`
- `neuroslice-control-dashboard.json`
- `neuroslice-mlops-dashboard.json`

## InfluxDB
Used for:
- telemetry/fault ingestion from telemetry pipeline
- AIOps measurement mirroring when enabled
- dashboard/operations time-series views

## ELK stack (`mlops` profile)
Assets exist for:
- index templates and ILM
- logstash canonical prediction ingestion pipeline
- Kibana provisioning scripts

## Prediction monitoring
Dashboard backend exposes:
- `/api/dashboard/mlops/monitoring/predictions`

Data path relies on Elasticsearch availability/config in `mlops` profile.

## Drift metrics
`aiops-drift-monitor` exposes Prometheus metrics at `/metrics` (when `drift` profile active), including:
- drift window size
- p-value
- drift detections count
- reference-loaded status

Online evaluation metrics:
- `neuroslice_aiops_eval_accuracy`
- `neuroslice_aiops_eval_precision`
- `neuroslice_aiops_eval_recall`
- `neuroslice_aiops_eval_f1`
- `neuroslice_aiops_eval_samples_total`
