# Smart Slice Observability

This folder contains observability assets for Smart Slice AIOps: Prometheus metrics scraping and an ELK stack for prediction monitoring.

## Prometheus

`prometheus.yml` configures Prometheus (started automatically with `docker compose up`) to scrape:

- `adapter-ves:7001/metrics` — VES adapter Prometheus metrics
- `adapter-netconf:7002/metrics` — NETCONF adapter Prometheus metrics
- `localhost:9090/metrics` — Prometheus self-metrics

Prometheus UI: `http://localhost:9090`

A Grafana datasource provisioning file at `grafana/provisioning/datasources/prometheus.yml` wires Prometheus into Grafana automatically (datasource UID `P1809F7CD0C75ACF3`).

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
