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
- `mlops-tier/drift-monitor`: lightweight anomaly-count drift detector that auto-triggers the MLOps pipeline
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

events.anomaly (sliding window count)
  -> mlops-drift-monitor (mlops-tier) -> mlops-runner /run-action -> offline pipeline trigger

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
