# 06 Drift

## Two drift systems

## 1) `mlops-tier` lightweight drift monitor (default runtime)
Service: `mlops-drift-monitor` (internal, port 8030 expose only)

Method:
- Counts anomaly events from `events.anomaly` over a sliding time window
- Triggers `mlops-runner` when threshold exceeded

Key variables:
- `DRIFT_ANOMALY_THRESHOLD` (default `5`)
- `DRIFT_WINDOW_SECONDS` (default `120`)
- `DRIFT_COOLDOWN_SECONDS` (default `600`)
- `DRIFT_POLL_INTERVAL_SECONDS` (default `30`)

Outputs:
- Redis drift status keys (`drift:status`, `drift:events`)
- Redis stream `events.drift`
- Runtime flag gate: `runtime:service:mlops-drift-monitor:*`

## 2) `aiops-tier` statistical drift monitor (optional `drift` profile)
Service: `aiops-drift-monitor` (host port `7012`)

Method:
- Alibi Detect **MMD** (`MMDDrift`)
- Per-model rolling windows from normalized telemetry

Key variables:
- `DRIFT_WINDOW_SIZE` (default `500`)
- `DRIFT_P_VALUE_THRESHOLD` (default `0.01`)
- `DRIFT_TEST_INTERVAL_SEC` (default `60`)
- `DRIFT_EMIT_COOLDOWN_SEC` (default `300`)

Required artifacts per promoted model:
- `drift_reference.npz`
- `drift_feature_schema.json`

Outputs:
- Redis state `aiops:drift:{model_name}`
- Redis stream `events.drift`
- Kafka topic `drift.alert`
- Prometheus metrics at `/metrics`
- Runtime flag gate: `runtime:service:aiops-drift-monitor:*`

## Dashboard drift visualization wiring
- MLOps drift pages call protected backend routes:
  - `/api/dashboard/mlops/drift`
  - `/api/dashboard/mlops/drift/{model_name}`
  - `/api/dashboard/mlops/drift-events`
- Control page drift panel uses:
  - `/api/dashboard/controls/drift/status`
  - `/api/dashboard/controls/drift/events`
  - `/api/dashboard/controls/drift/trigger` (write-role restricted)

## Practical distinction
- `mlops-drift-monitor`: orchestration trigger mechanism (anomaly burst proxy)
- `aiops-drift-monitor`: statistical drift detector with reference-based MMD
