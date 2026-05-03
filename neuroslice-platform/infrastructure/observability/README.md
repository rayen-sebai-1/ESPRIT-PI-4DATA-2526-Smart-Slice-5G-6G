# Smart Slice Observability

Last verified: 2026-04-30.

This folder contains observability assets for Smart Slice AIOps: Prometheus metrics scraping and an ELK stack for prediction monitoring.

## Prometheus

`prometheus.yml` configures Prometheus (started automatically with `docker compose up`) to scrape all critical Scenario B services:

- `adapter-ves:7001/metrics`
- `adapter-netconf:7002/metrics`
- `congestion-detector:9101/metrics`
- `sla-assurance:9102/metrics`
- `slice-classifier:9103/metrics`
- `online-evaluator:7013/metrics`
- `alert-management:7010/metrics`
- `policy-control:7011/metrics`
- `dashboard-backend:8002/metrics`
- `api-bff-service:8000/metrics`
- `mlops-runner:8020/metrics`
- `mlops-drift-monitor:8030/metrics`
- `aiops-drift-monitor:7012/metrics` (active when `--profile drift` is used)
- `localhost:9090/metrics` (Prometheus self-metrics)

Prometheus UI: `http://localhost:9090`

### Scenario B Metrics Coverage

The following metric families are source-wired:

- AIOps workers:
  - `neuroslice_aiops_events_processed_total`
  - `neuroslice_aiops_predictions_total`
  - `neuroslice_aiops_fallback_mode`
  - `neuroslice_aiops_model_loaded`
  - `neuroslice_aiops_last_event_timestamp`
  - `neuroslice_aiops_inference_latency_seconds`
  - `neuroslice_aiops_service_enabled`
- Control tier:
  - `neuroslice_control_alerts_total`
  - `neuroslice_control_actions_total`
  - `neuroslice_control_events_processed_total`
  - `neuroslice_control_last_event_timestamp`
- Dashboard/backend:
  - `neuroslice_dashboard_requests_total`
  - `neuroslice_dashboard_request_latency_seconds`
  - `neuroslice_dashboard_mlops_pipeline_requests_total`
  - `neuroslice_dashboard_auth_failures_total`
- MLOps:
  - `neuroslice_mlops_runner_requests_total`
  - `neuroslice_mlops_runner_duration_seconds`
  - `neuroslice_mlops_runner_enabled`
  - `neuroslice_mlops_drift_anomaly_events_total`
  - `neuroslice_mlops_drift_triggers_total`
  - `neuroslice_mlops_drift_last_trigger_timestamp`
  - `neuroslice_mlops_drift_enabled`
  - `neuroslice_mlops_kafka_drift_messages_total{result}` (result: `accepted` | `no_drift` | `severity_filtered` | `auto_trigger_off` | `duplicate` | `cooldown` | `error`)
  - `neuroslice_mlops_cron_retraining_triggers_total{model,status}` (status: `created` | `duplicate` | `disabled`)
- Online evaluator:
  - `neuroslice_aiops_eval_accuracy`
  - `neuroslice_aiops_eval_precision`
  - `neuroslice_aiops_eval_recall`
  - `neuroslice_aiops_eval_f1`
  - `neuroslice_aiops_eval_samples_total`

### Drift Detection Metrics (drift profile)

When the `drift` profile is active, the following metrics are exposed:

| Metric | Type | Description |
|--------|------|-------------|
| `neuroslice_drift_window_size{model_name}` | Gauge | Current rolling window sample count |
| `neuroslice_drift_p_value{model_name}` | Gauge | Latest MMD p-value |
| `neuroslice_drift_detected_total{model_name}` | Counter | Total drift detections |
| `neuroslice_drift_reference_loaded{model_name}` | Gauge | 1 if reference artifact loaded |
| `neuroslice_drift_last_check_timestamp{model_name}` | Gauge | Unix timestamp of last check |
| `neuroslice_drift_events_emitted_total{model_name}` | Counter | Total drift alert events published |

A Grafana datasource provisioning file at `grafana/provisioning/datasources/prometheus.yml` wires Prometheus into Grafana automatically (datasource UID `P1809F7CD0C75ACF3`).

## Grafana Dashboards

Scenario B dashboards are provisioned from `infrastructure/observability/grafana/dashboards/`:

- `neuroslice-platform-overview.json`
- `neuroslice-aiops-dashboard.json`
- `neuroslice-control-dashboard.json`
- `neuroslice-mlops-dashboard.json`

Dashboard provisioning maps this folder to `/etc/grafana/dashboards`, and Grafana default home is set to:

- `/etc/grafana/dashboards/neuroslice-platform-overview.json`

---

## ELK Stack (Prediction Monitoring)

The ELK section contains production-oriented observability assets for Smart Slice AIOps prediction monitoring.


## What This Setup Delivers

- Normalized Logstash ingestion with ECS v8 canonical fields:
  - `service.name`
  - `ml.model`, `ml.model_version`, `ml.model_type`
  - `ml.prediction`
  - `ml.confidence`
  - `ecs.version`, `event.category`, `event.type`, `event.action`, `event.ingested`
- Raw inbound JSON preserved in `event.original`
- Parsed event body preserved under `payload.*`
- Elasticsearch template + ILM policy for `smart-slice-predictions*`
- Kibana data view, visualizations, and dashboard provisioning script

## Canonical Document Schema

```json
{
  "@timestamp": "2026-04-26T20:00:00.000Z",
  "ecs": {
    "version": "8.11"
  },
  "service": {
    "name": "congestion-detector"
  },
  "ml": {
    "model": "congestion_5g",
    "prediction": "anomaly",
    "confidence": 0.92
  },
  "event": {
    "dataset": "smart_slice.predictions",
    "kind": "event",
    "module": "smart_slice",
    "category": "web",
    "type": "info",
    "action": "ml-prediction",
    "ingested": "2026-04-26T20:00:01.234Z",
    "original": "{...original raw JSON body...}"
  },
  "observer": {
    "name": "neuroslice-logstash",
    "type": "logstash",
    "version": "8.13.4"
  },
  "message": "congestion-detector predicted anomaly (confidence=0.920)",
  "payload": {
    "service": "congestion-detector",
    "model": "congestion_5g",
    "prediction": "anomaly",
    "confidence": 0.92
  }
}
```

## 1) Apply Elasticsearch Schema + ILM

From `neuroslice-platform/infrastructure`:

```bash
python observability/elasticsearch/provision_smart_slice_schema.py --es-url http://localhost:9200
```

This command:

- Creates/updates ILM policy `smart-slice-predictions-ilm`
- Creates/updates index template `smart-slice-predictions-template`
- Updates current index mapping/settings for `smart-slice-predictions`

## 2) Recreate Logstash to Apply Pipeline Changes

From `neuroslice-platform/infrastructure`:

```bash
docker compose --profile mlops up -d --force-recreate logstash
```

## 3) Provision Kibana Visualizations + Dashboard

From `neuroslice-platform/infrastructure`:

```bash
python observability/kibana/provision_smart_slice_dashboard.py --kibana-url http://localhost:5601
```

Visualizations created:

- `Predictions Over Time` (line chart)
- `Prediction Distribution` (pie chart)
- `Predictions Per Service` (bar chart)
- `Total Predictions` (metric)
- `Average Confidence` (metric)

Dashboard created:

- `Smart Slice AIOps Observability`

## 4) Add Dashboard Filter Controls (Recommended)

The dashboard uses time-range filtering and query bar by default.

To add dedicated dropdown filters in Kibana UI:

1. Open the dashboard in Edit mode.
2. Click `Controls` then `Add control`.
3. Add options list controls for:
   - `service.name.keyword`
   - `ml.model.keyword`
   - `ml.prediction.keyword`
4. Save the dashboard.

## 5) Verification Checklist

- `curl -X POST http://localhost:8081 -H "Content-Type: application/json" -d '{"test":true}'` returns `ok`
- New documents have:
  - `ecs.version`
  - `service.name`
  - `ml.model`, `ml.prediction`, `ml.confidence`
  - `event.original` (raw JSON string)
  - `event.ingested`, `event.action`
  - `payload.*` (parsed input fields)
- Kibana Discover data view pattern: `smart-slice-predictions*`
- Dashboard panels are populated when prediction events arrive

## 6) Index and Naming Conventions (Recommended)

- Keep a functional prefix by domain: `smart-slice-predictions*`
- Keep dataset names ECS-friendly: `smart_slice.predictions`
- Use field naming by intent:
  - dimensions: keywords (`service.name`, `ml.model`, `ml.prediction`)
  - metrics: numeric (`ml.confidence`, `latency_ms`)
  - original payload: `payload.*`

## 7) ILM Recommendations

Current policy is conservative and safe for demo + production pilots:

- Hot: immediate ingest
- Warm after 7d: force-merge and lower priority
- Delete after 30d

For larger production volumes, move to rollover-based indexing (`smart-slice-predictions-000001` + write alias) and increase retention windows.
