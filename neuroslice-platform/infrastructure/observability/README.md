# Smart Slice Observability (ELK)

This folder contains production-oriented observability assets for Smart Slice AIOps prediction monitoring.

## What This Setup Delivers

- Normalized Logstash ingestion with canonical fields:
  - `service.name`
  - `ml.model`
  - `ml.prediction`
  - `ml.confidence`
  - top-level compatibility fields: `model`, `prediction`, `confidence`
- Raw inbound body preserved under `payload.raw`
- Parsed event body preserved under `payload.*`
- Elasticsearch template + ILM policy for `smart-slice-predictions*`
- Kibana data view, visualizations, and dashboard provisioning script

## Canonical Document Schema

```json
{
  "@timestamp": "2026-04-26T20:00:00.000Z",
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
    "module": "smart_slice"
  },
  "message": "congestion-detector predicted anomaly (confidence=0.920)",
  "payload": {
    "raw": "{...original raw HTTP body...}",
    "service": {
      "name": "congestion-detector"
    },
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

- `curl http://localhost:8081` returns `ok`
- New documents have:
  - `service.name`
  - `ml.model`
  - `ml.prediction`
  - `ml.confidence`
  - `payload.raw`
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
