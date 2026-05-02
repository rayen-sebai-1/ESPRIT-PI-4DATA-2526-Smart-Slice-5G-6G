# NeuroSlice Platform

Last verified: 2026-04-30.

`neuroslice-platform/` is the runnable platform subtree. It contains the integrated Docker Compose runtime, all service tiers, and the MLOps project used to train and promote models for online AIOps.

## Scenario B Validation Scope (Current)

- Active validation target: Docker Compose local PoC for simulation, ingestion, AIOps (except misrouting), MLOps, control, API/dashboard, and observability
- Explicitly out of scope in this validation pass: `agentic-ai-tier`
- Explicitly deferred/future work: `misrouting-detector`
- Agentic AI tier is implemented but excluded from current Scenario B validation scope.

## Current Tiers

Implemented:

- `simulation-tier`: Core, Edge, and RAN simulators plus `fault-engine`
- `ingestion-tier`: VES adapter, NETCONF adapter, normalizer, telemetry exporter, shared models/config
- `aiops-tier`: `congestion-detector`, `slice-classifier`, `sla-assurance`, optional `aiops-drift-monitor` (profile `drift`), `online-evaluator`, and shared model-loading utilities
- `api-dashboard-tier`: BFF (with Redis Live State endpoints), auth service, dashboard backend, Kong gateway, and React dashboard
- `control-tier`: `alert-management` and `policy-control` — deterministic alert lifecycle and human-in-the-loop remediation
- `agentic-ai-tier`: `root-cause` and `copilot-agent`
- `mlops-tier/batch-orchestrator`: offline data, training, MLflow, ONNX/FP16 export, promotion, API, tests, and reports
- `mlops-tier/mlops-runner`: internal-only worker that executes the offline pipeline on behalf of the dashboard
- `mlops-tier/drift-monitor`: lightweight anomaly-count drift detector that creates retraining approval requests
- `infrastructure`: integrated Compose stack

Deferred:

- `misrouting-detector` is not implemented as an online AIOps worker.

## Default Runtime

`docker compose up --build` from `infrastructure/` starts:

- Redis, Zookeeper, Kafka, InfluxDB, PostgreSQL, Grafana
- `adapter-ves`, `adapter-netconf`, `normalizer`, `telemetry-exporter`
- `simulator-core`, `simulator-edge`, `simulator-ran`, `fault-engine`
- `congestion-detector`, `slice-classifier`, `sla-assurance`
- `online-evaluator`
- `api-bff-service`, `auth-service`, `dashboard-backend`, `kong-gateway`, `react-dashboard`
- `root-cause`, `copilot-agent`
- `alert-management`, `policy-control`
- `mlops-runner` (internal — no published port)
- `mlops-drift-monitor` (mlops-tier lightweight drift detector at port 8030, internal)

Optional `drift` profile adds:

- `aiops-drift-monitor` (aiops-tier statistical drift detector with alibi-detect, port 7012)

Optional `mlops` profile adds:

- `mlops-postgres`, `minio`, `minio-init`, `mlflow-server`, `elasticsearch`, `logstash`, `kibana`, `mlops-api`
- `logstash-aiops-ingest` (Logstash -> Redis `stream:norm.telemetry` real-time bridge for AIOps workers)

Optional `mlops-worker` profile runs the offline pipeline manually.

## End-to-End Data Flow

```text
simulator-core / simulator-ran -> adapter-ves -> stream:raw.ves
simulator-edge                 -> adapter-netconf -> stream:raw.netconf

stream:raw.ves + stream:raw.netconf
  -> normalizer
  -> stream:norm.telemetry
  -> entity:{entity_id}
  -> Kafka topic telemetry-norm

stream:norm.telemetry
  -> congestion-detector -> events.anomaly -> aiops:congestion:{entity_id}
  -> slice-classifier    -> events.slice.classification -> aiops:slice_classification:{entity_id}
  -> sla-assurance       -> events.sla -> aiops:sla:{entity_id}
  -> aiops-drift-monitor -> events.drift -> aiops:drift:{model_name}   (aiops-tier, drift profile)
events.anomaly + events.sla + events.slice.classification + stream:norm.telemetry
  -> online-evaluator -> events.evaluation -> aiops:evaluation:{model_name}

events.anomaly + events.sla + events.slice.classification
  -> alert-management -> stream:control.alerts
  -> policy-control   -> stream:control.actions
  -> policy-control simulated actuator -> stream:control.actuations + control:sim:* keys

events.anomaly / events.sla / events.slice.classification (sliding window anomaly count)
  -> mlops-drift-monitor (mlops-tier) -> Redis pending retraining request
  -> dashboard approval API (/mlops/requests/{id}/approve + /execute)
  -> mlops-runner /run-action -> offline model-specific pipeline

telemetry-norm -> telemetry-exporter -> InfluxDB

api-bff-service -> Redis state, streams, fault-engine, and Live State
react-dashboard -> kong-gateway -> auth-service / dashboard-backend
root-cause / copilot-agent -> Redis, InfluxDB, Ollama/LangChain tools
```

## Runtime Service Controls

Scenario B runtime controls are Redis-backed feature flags (no container lifecycle control from dashboard):

- `runtime:service:{service_name}:enabled`
- `runtime:service:{service_name}:mode`
- `runtime:service:{service_name}:updated_at`
- `runtime:service:{service_name}:updated_by`
- `runtime:service:{service_name}:reason`

## Model Deployment Flow

The offline MLOps pipeline exports ONNX and FP16 ONNX artifacts, promotes quality-gate-passing models, and updates production pointers under:

```text
mlops-tier/batch-orchestrator/models/promoted/{model_name}/current/
```

Runtime AIOps services mount that directory as `/mlops/models/promoted/...` and load `current/model_fp16.onnx` with ONNX Runtime. Services poll `current/metadata.json` and hot reload when the version or file timestamp changes.

Configured model names in Compose:

- `congestion-detector`: `congestion_5g`
- `slice-classifier`: `slice_type_5g`
- `sla-assurance`: `sla_5g`

## Human-in-the-Loop MLOps Control

Retraining now follows a strict approval flow:

1. Drift monitor detects anomaly bursts and creates a Redis request with `status=pending_approval`.
2. Dashboard control plane lists requests at `/mlops/requests`.
3. Admin user approves (`/mlops/requests/{id}/approve`) or rejects (`/mlops/requests/{id}/reject`).
4. Admin explicitly executes approved requests (`/mlops/requests/{id}/execute`).
5. Execution calls `mlops-runner` only after control checks (per-model lock, global concurrency limit, cooldown).

Automatic direct retraining from drift detection is disabled by default with `AUTO_RETRAIN_ENABLED=false`.
The dashboard is the execution control plane for retraining.

## Quick Start

```bash
cd neuroslice-platform/infrastructure
docker compose up --build
```

Useful checks:

```bash
curl http://localhost:8000/health
curl http://localhost:7001/health
curl http://localhost:7002/health
curl http://localhost:7004/health
curl http://localhost:7005/health
curl http://localhost:7006/health
curl "http://localhost:8000/api/v1/aiops/congestion/latest?limit=20"
curl http://localhost:8000/api/v1/live/overview
curl "http://localhost:8000/api/v1/live/entities?limit=10"
```

Optional MLOps services:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops up --build
```

## Real-time Logstash → Models validation

This section validates the real-time path from Logstash to the runtime AIOps model services without removing the existing batch/offline MLOps behavior.

### 1. Start the required runtime

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops up --build
```

### 2. Verify service/network contracts by inspection

- `infrastructure/docker-compose.yml`:
  - `logstash`, `logstash-aiops-ingest`, `redis`, and AIOps workers are on the same Compose default network.
  - `logstash` outputs to service name `logstash-aiops-ingest:7014` (not localhost).
  - `logstash-aiops-ingest` publishes to `stream:norm.telemetry` (same stream consumed by `congestion-detector`, `sla-assurance`, `slice-classifier`).
  - `logstash-aiops-ingest` is internal-only (`expose: 7014`, no host-published port).
  - `logstash` depends on `logstash-aiops-ingest` health.
- `mlops-tier/batch-orchestrator/logstash/pipeline/logstash.conf`:
  - keeps/normalizes: `timestamp`, `slice_id`, `cell_id`, `gnb_id`, `metric_name`, `metric_value`, `anomaly_score`, `prediction`, `source_service`, `event_id`
  - writes to Elasticsearch and forwards JSON events to `http://logstash-aiops-ingest:7014/ingest/logstash`.
- `ingestion-tier/logstash-aiops-ingest/main.py`:
  - validates event schema, rejects malformed/stale events with explicit `422` details
  - logs structured receive/forward records with `event_id`, `slice_id`, `timestamp`, `source_service`
  - publishes canonical events to Redis `stream:norm.telemetry`.

### 3. Send a sample event through Logstash

```bash
cd neuroslice-platform
docker compose -f infrastructure/docker-compose.yml --profile mlops exec mlops-api \
  python src/monitoring/send_aiops_prediction_example.py
```

### 4. Confirm immediate model consumption

- Check `congestion-detector`, `sla-assurance`, `slice-classifier` logs for `prediction_step` lines containing:
  - `event_id`
  - `source_event_id`
  - `slice_id`
  - `timestamp`
  - `source_service`
  - `freshness_seconds`
- Check `logstash` logs for `logstash_output` JSON lines.
- Check `logstash-aiops-ingest` logs for `model_receive` and `model_receive_forwarded`.
- If Logstash fails to start with an output plugin error, install plugin `logstash-output-http` in the Logstash image and restart.

### 5. Confirm downstream persistence/publication

- Redis streams:
  - input to models: `stream:norm.telemetry`
  - model outputs: `events.anomaly`, `events.sla`, `events.slice.classification`
- Elasticsearch:
  - predictions are still indexed in `logs-smart_slice.predictions-default` data stream.
- Dashboard/BFF:
  - recent AIOps outputs remain visible via existing API routes that read Redis state/streams.

### 6. Contract notes

- Required receive fields: `event_id`, `timestamp`, `source_service`, plus at least one signal field among `metric_name`, `metric_value`, `anomaly_score`, `prediction`, `kpis`.
- Freshness guard: events older than `LOGSTASH_EVENT_MAX_AGE_SECONDS` are rejected with `422 stale_event`.
- Both real-time and batch/offline paths remain active:
  - batch/offline: `mlops-worker` / training pipeline
  - real-time: Logstash -> `logstash-aiops-ingest` -> `stream:norm.telemetry` -> AIOps workers

Optional drift detection:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile drift up --build
```

Manual offline pipeline:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops --profile mlops-worker run --rm mlops-worker
```

## Important URLs

- Public API/BFF: `http://localhost:8000`
- VES adapter: `http://localhost:7001`
- NETCONF adapter: `http://localhost:7002`
- Fault engine: `http://localhost:7004`
- Root-cause agent: `http://localhost:7005`
- Copilot agent: `http://localhost:7006`
- aiops-drift-monitor API/metrics: `http://localhost:7012` with `drift` profile
- mlops-drift-monitor: internal-only service (`mlops-drift-monitor:8030` on the Compose network; no host-published port)
- React dashboard: `http://localhost:5173`
- React live-state overview: `http://localhost:5173/live-state`
- Kong gateway: `http://localhost:8008`
- Grafana: `http://localhost:3000`
- InfluxDB: `http://localhost:8086`
- MLflow UI: `http://localhost:5000` with `mlops` profile
- MinIO API: `http://localhost:9000` with `mlops` profile
- MinIO console: `http://localhost:9001` with `mlops` profile
- MLOps API: `http://localhost:8010` with `mlops` profile
- Elasticsearch: `http://localhost:9200` with `mlops` profile
- Kibana: `http://localhost:5601` with `mlops` profile

## Repository Map

```text
neuroslice-platform/
|-- agentic-ai-tier/
|-- aiops-tier/
|-- api-dashboard-tier/
|-- control-tier/
|   |-- alert-management/
|   `-- policy-control/
|-- infrastructure/
|-- ingestion-tier/
|-- mlops-tier/
|   |-- batch-orchestrator/
|   |-- drift-monitor/
|   `-- mlops-runner/
`-- simulation-tier/
```

## Generated Files

Training and runtime outputs are local artifacts. Important generated paths include:

- `mlops-tier/batch-orchestrator/models/registry.json`
- `mlops-tier/batch-orchestrator/models/promoted/`
- `mlops-tier/batch-orchestrator/models/onnx/`
- `mlops-tier/batch-orchestrator/data/processed/`
- `mlops-tier/batch-orchestrator/reports/model_training_summary.md`

These files may be present in a running workspace but should be treated as generated runtime outputs, not source code.
