# NeuroSlice Platform

End-to-end 5G/6G network-slicing simulation and MLOps platform.

This folder contains the runnable multi-service simulator stack (Core/Edge/RAN + fault injection + ingestion + API + observability) and a separate MLOps training/inference stack for slice intelligence models.

## 1) What This Repository Implements Today

The implemented platform is centered around these active tiers:

- `simulation-tier`: SimPy-based telecom domain simulators + fault engine + scenario files.
- `ingestion-tier`: VES/NETCONF adapters, normalization pipeline, Redis/Kafka bridge, Influx exporter.
- `aiops-tier`: online runtime inference services for:
  - `congestion-detector`
  - `slice-classifier`
  - `sla-assurance`
- `api-dashboard-tier/api-bff-service`: public FastAPI for KPI queries, streaming, and runtime AIOps result access.
- `api-dashboard-tier/auth-service`: canonical dashboard auth entry for Scenario B.
- `api-dashboard-tier/kong-gateway`: canonical dashboard gateway entry for Scenario B.
- `api-dashboard-tier/react-dashboard`: canonical dashboard frontend entry for Scenario B.
- `api-dashboard-tier/dashboard-backend`: canonical protected dashboard domain API backend.
- `infrastructure`: Docker Compose runtime, Redis/Kafka/Zookeeper/InfluxDB/Grafana observability.
- `mlops-tier/batch-orchestrator`: data preprocessing, model training, model-serving API, tests, MLflow integration.

Present but currently scaffold-only or pending:

- `agentic-ai-tier/`
- `control-tier/`
- `infrastructure/k8s/`
- `infrastructure/istio/`

Deferred in this iteration:

- `aiops-tier/misrouting-detector`

## 2) High-Level Architecture

```text
Simulators (Core / Edge / RAN)
  -> adapter-ves (/events) + adapter-netconf (/telemetry)
  -> Redis Streams (stream:raw.ves, stream:raw.netconf)
  -> normalizer (canonical event mapping)
  -> Redis Stream stream:norm.telemetry + Redis hashes entity:{id}
  -> Kafka topic telemetry-norm

telemetry-norm / stream:norm.telemetry
  -> congestion-detector
  -> slice-classifier
  -> sla-assurance

AIOps runtime outputs
  -> Redis state updates
  -> Kafka events.anomaly / events.sla / events.slice.classification
  -> optional InfluxDB prediction/event measurements
  -> api-bff-service

telemetry-exporter
  -> InfluxDB measurement telemetry + faults

api-bff-service
  -> reads Redis streams/hashes for KPIs and AIOps outputs
  -> proxies fault/scenario calls to fault-engine
  -> exposes SSE stream /api/v1/stream/kpis
```

## 3) Runtime Service Topology (Docker Compose)

Compose file: `infrastructure/docker-compose.yml`

### Infrastructure services

- `redis` (`6379` external configurable via `REDIS_PORT`)
- `zookeeper`
- `kafka` (`29092` host listener)
- `influxdb` (`8086`)
- `grafana` (`3000`)

### Application services

- `simulator-core`
- `simulator-edge`
- `simulator-ran`
- `fault-engine` (`7004`)
- `adapter-ves` (`7001`)
- `adapter-netconf` (`7002`)
- `normalizer` (no HTTP port)
- `telemetry-exporter` (no HTTP port)
- `congestion-detector`
- `slice-classifier`
- `sla-assurance`
- `api-bff-service` (`8000`)

### Shared runtime behavior

- All Python services mount `../simulation-tier/scenarios` to `/scenarios` as read-only.
- Simulators and services use `ingestion-tier/shared` for shared config, models, and Redis helpers.
- Grafana is pre-provisioned with an InfluxDB datasource and dashboard JSON.

## 4) Core Domain Simulation Model

The simulator runs three telecom domains with stateful latent-variable updates per tick.

### Core domain entities

- `amf-01` (`AMFState`)
- `smf-01` (`SMFState`)
- `core-upf-01` (`UPFState`)

### Edge domain entities

- `edge-upf-01` (`EdgeUPFState`)
- `mec-app-01` (`MECAppState`)
- `edge-comp-01` (`ComputeNodeState`)

### RAN domain topology

- `2` gNBs (`gnb-01`, `gnb-02`)
- each with `2` cells
- each cell with `3` slices: `eMBB`, `URLLC`, `mMTC`
- total slice instances: `12`

### Simulation timing

- `TICK_INTERVAL_SEC` controls real-world sleep between engine steps.
- `SIM_SPEED` converts tick progression into simulated seconds for traffic patterns.
- Engines run SimPy and bridge it with asyncio.

### Cross-domain shared state in Redis

- `ran:congestion_score` written by RAN, consumed by Core + Edge.
- `core:active_ues` written by RAN.
- `edge:saturation`, `edge:misrouting_ratio` written by Edge.

## 5) Fault Engine and Scenario System

Fault engine service (`simulation-tier/fault-engine/main.py`) manages active faults in Redis and scenario execution.

### Redis fault state

- Active faults stored in hash: `faults:active`
- Fault lifecycle events streamed to: `stream:fault.events`

### Fault APIs (fault-engine direct)

- `GET /health`
- `GET /faults/active`
- `GET /scenarios`
- `POST /scenarios/start`
- `POST /scenarios/stop`
- `POST /faults/inject`

### Built-in scenario files (`simulation-tier/scenarios`)

- `normal_day`: 24h baseline, no faults.
- `peak_hour`: 1.8x traffic + `ran_congestion`.
- `urllc_misrouting`: URLLC path/QoS mismatch + added latency/loss.
- `edge_degradation`: edge overload + latency amplification.
- `cascading_incident`: multi-domain combined fault chain.

### Fault types declared in shared model enum

- `ran_congestion`
- `edge_overload`
- `amf_degradation`
- `upf_overload`
- `packet_loss_spike`
- `latency_spike`
- `telemetry_drop`
- `malformed_telemetry`
- `slice_misrouting`

Note: not all enum fault types are currently consumed by all engines; only implemented ones affect KPI state today.

## 6) Ingestion and Canonical Telemetry Pipeline

### Adapters

#### VES adapter (`ingestion-tier/adapter-ves`)

- Endpoint: `POST /events`
- Reads simulator VES-like payloads.
- Simulates malformed rejection (~5%) and increments Prometheus counters.
- Publishes accepted raw payloads to `stream:raw.ves`.
- Endpoints: `/health`, `/metrics`, `/events`.

#### NETCONF adapter (`ingestion-tier/adapter-netconf`)

- Endpoint: `POST /telemetry`
- Flattens NETCONF-style hierarchical blobs into flat section records.
- Simulates schema mismatch (~3%) by renaming `forwardingLatencyMs` to `delay_ms`.
- Publishes flattened records to `stream:raw.netconf`.
- Endpoints: `/health`, `/metrics`, `/telemetry`.

### Normalizer (`ingestion-tier/normalizer`)

Consumes `stream:raw.ves` + `stream:raw.netconf` through Redis consumer groups and emits:

- canonical events to `stream:norm.telemetry`
- latest per-entity state in Redis hash `entity:{entity_id}`
- mirrored canonical payload to Kafka topic `telemetry-norm`

Canonical event model is defined in `ingestion-tier/shared/models.py` (`CanonicalEvent`) with:

- identity: `eventId`, `timestamp`, `siteId`, `nodeId`, `entityId`, `entityType`
- topology: `domain`, optional `sliceId`, optional `sliceType`
- metrics: `kpis`, `derived` (`congestionScore`, `healthScore`, `misroutingScore`)
- optional routing info: `expectedUpf`, `actualUpf`, `qosProfileExpected`, `qosProfileActual`
- scenario/severity metadata

### Telemetry exporter (`ingestion-tier/telemetry-exporter`)

- Consumes Kafka topic `telemetry-norm`.
- Writes telemetry points to InfluxDB measurement `telemetry`.
- Polls Redis `faults:active` every 5s and writes InfluxDB measurement `faults`:
  - aggregate point (`active_count`)
  - per-fault points (`severity`, `fault_type`, `scenario_id`, etc.)

## 7) AIOps Runtime Tier

The `aiops-tier` implements online inference services for the Docker Compose runtime.

### Services

#### `congestion-detector`

- Consumes normalized telemetry events.
- Builds congestion-related features from canonical KPIs.
- Runs live model inference.
- Publishes congestion/anomaly events.
- Updates current congestion-related state in Redis.
- Optionally persists prediction outputs to InfluxDB.

#### `slice-classifier`

- Consumes normalized telemetry events.
- Predicts or validates slice classification from live telemetry features.
- Publishes classification outputs.
- Updates slice/entity state in Redis.
- Optionally persists classification outputs to InfluxDB.

#### `sla-assurance`

- Consumes normalized telemetry events.
- Computes SLA risk / SLA-related prediction outputs.
- Publishes SLA events.
- Updates SLA-related state in Redis.
- Optionally persists results to InfluxDB.

### Notes

- `misrouting-detector` is intentionally deferred in this iteration.
- The runtime AIOps tier is designed for Scenario B (Docker Compose PoC).
- Kubernetes/Istio deployment concerns are intentionally out of scope for this stage.

### Runtime model loading

- `congestion-detector` loads:
  - `/mlops/models/congestion_5g_lstm_traced.pt`
  - `/mlops/data/processed/preprocessor_congestion_5g.pkl`
- `slice-classifier` loads latest local registry metadata for `slice-type-lgbm-5g` from:
  - `/mlops/mlflow.db`
  - `/mlops/mlruns/.../model.pkl`
  - `/mlops/data/processed/label_encoder_slice_type_5g.pkl`
- `sla-assurance` loads latest local registry metadata for `sla-xgboost-5g` from:
  - `/mlops/mlflow.db`
  - `/mlops/mlruns/.../model.ubj`
  - `/mlops/data/processed/scaler_sla_5g.pkl`
- If model artifacts are unavailable, services continue running with heuristic fallback inference and explicit warning logs.

## 8) Runtime AIOps Output Contracts

The runtime AIOps tier emits derived events and state updates based on normalized telemetry.

### Kafka / stream outputs

Implemented outputs include:

- `events.anomaly`
- `events.sla`
- `events.slice.classification`

### Common event fields

Runtime AIOps outputs should include fields such as:

- `eventId`
- `timestamp`
- `service`
- `siteId`
- `sliceId`
- `entityId`
- `severity`
- `score`
- `prediction`
- `modelVersion`
- `sourceEventId`

### State updates

Services may also update Redis keys/hashes for latest runtime inference state to support fast reads from the API/BFF.

## 9) API/BFF Service

Service: `api-dashboard-tier/api-bff-service/main.py`

### Health/config

- `GET /health`
- `GET /config`

### KPI query endpoints

- `GET /api/v1/kpis/latest`
- `GET /api/v1/kpis/recent`
- `GET /api/v1/kpis/entity/{entity_id}`

### Streaming endpoint

- `GET /api/v1/stream/kpis` (Server-Sent Events from `stream:norm.telemetry`)

### Runtime AIOps query endpoints

- `GET /api/v1/aiops/congestion/latest`
- `GET /api/v1/aiops/sla/latest`
- `GET /api/v1/aiops/slice-classification/latest`
- `GET /api/v1/aiops/events/recent` (`stream` query supports `events.anomaly`, `events.sla`, `events.slice.classification`)

### Scenario/fault proxy endpoints (to fault-engine)

- `GET /api/v1/faults/active`
- `POST /api/v1/scenarios/start`
- `POST /api/v1/scenarios/stop`
- `POST /api/v1/faults/inject`

### ML-oriented export endpoints

- `GET /api/v1/export/sla`
- `GET /api/v1/export/slice-classifier`
- `GET /api/v1/export/congestion-sequences`

## 10) Redis, Kafka, and Influx Data Contracts

### Redis streams

- `stream:raw.ves`
- `stream:raw.netconf`
- `stream:norm.telemetry`
- `stream:fault.events`
- `events.anomaly`
- `events.sla`
- `events.slice.classification`

### Redis hashes/keys

- `faults:active` (active fault JSON objects)
- `entity:{entity_id}` (latest canonicalized state snapshot)
- `ran:congestion_score`, `core:active_ues`, `edge:saturation`, `edge:misrouting_ratio`
- `aiops:congestion:{entity_id}`
- `aiops:sla:{entity_id}`
- `aiops:slice_classification:{entity_id}`

### Kafka

- broker: `kafka:9092` inside compose network
- topic: `telemetry-norm`
- topics (runtime AIOps outputs): `events.anomaly`, `events.sla`, `events.slice.classification`

### InfluxDB

- bucket: `telemetry`
- measurement `telemetry`:
  - tags: `domain`, `entity_id`, `entity_type`, `slice_id`, `slice_type`
  - fields: KPI fields prefixed `kpi_`, derived fields prefixed `derived_`, and `severity`
- measurement `faults`:
  - aggregate `active_count`
  - per-fault severity/status and tags
- measurement `aiops_congestion`: runtime congestion score/prediction outputs
- measurement `aiops_sla`: runtime SLA risk outputs
- measurement `aiops_slice_classification`: runtime slice classification outputs

## 11) Observability

### Grafana provisioning

- datasource file: `infrastructure/observability/grafana/provisioning/datasources/influxdb.yml`
- dashboard provider: `.../dashboards/dashboards.yml`
- dashboard JSON: `.../dashboards/neuroslice_overview.json`

### Dashboard coverage includes

- system overview cards (RAN/Edge/Core max congestion, misrouting score, active faults, event count)
- RAN panels (RB utilization, slice latency)
- Edge panels (forwarding latency, CPU)
- Core panels (active UEs, core UPF throughput)
- Health/misrouting trend panels

## 12) Environment Variables

File: `infrastructure/.env.example`

| Variable | Purpose | Default |
|---|---|---|
| `SITE_ID` | site identity in generated events | `TT-SFAX-02` |
| `TICK_INTERVAL_SEC` | real-time sleep per simulation tick | `2.0` |
| `SIM_SPEED` | simulated seconds per real second | `60.0` |
| `REDIS_PORT` | host-mapped Redis port | `6379` |
| `STREAM_MAXLEN` | Redis stream retention maxlen | `10000` |
| `CONGESTION_THRESHOLD` | congestion anomaly threshold for runtime inference | `0.5` |
| `SLICE_MISMATCH_CONFIDENCE_THRESHOLD` | confidence threshold for slice mismatch severity | `0.8` |
| `SLA_RISK_THRESHOLD` | SLA risk threshold (`sla_at_risk` cutover) | `0.5` |
| `API_PORT` | host API/BFF port | `8000` |
| `VES_PORT` | host adapter-ves port | `7001` |
| `NETCONF_PORT` | host adapter-netconf port | `7002` |
| `FAULT_ENGINE_PORT` | host fault-engine port | `7004` |
| `EXPORTER_PORT` | reserved (not bound by compose) | `9091` |
| `PROMETHEUS_PORT` | reserved (Prometheus not in compose) | `9090` |
| `GRAFANA_PORT` | host Grafana port | `3000` |
| `GRAFANA_USER` | Grafana admin username | `admin` |
| `GRAFANA_PASSWORD` | Grafana admin password | `neuroslice` |

Additional static defaults currently hardcoded in compose:

- InfluxDB init user/password/token/org/bucket
- Kafka host listener mapping `localhost:29092`
- AIOps model and preprocessing mounts via `/mlops`:
  - `CONGESTION_MODEL_PATH=/mlops/models/congestion_5g_lstm_traced.pt`
  - `CONGESTION_PREPROCESSOR_PATH=/mlops/data/processed/preprocessor_congestion_5g.pkl`
  - `SLICE_MODEL_NAME=slice-type-lgbm-5g`
  - `SLICE_LABEL_ENCODER_PATH=/mlops/data/processed/label_encoder_slice_type_5g.pkl`
  - `SLA_MODEL_NAME=sla-xgboost-5g`
  - `SLA_SCALER_PATH=/mlops/data/processed/scaler_sla_5g.pkl`
  - `MLFLOW_DB_PATH=/mlops/mlflow.db`
  - `MLRUNS_DIR=/mlops/mlruns`

## 13) Quick Start (Simulation + API + Observability)

From repo root:

```bash
cd neuroslice-platform/infrastructure
cp .env.example .env
docker compose up --build
```

Verify:

```bash
curl http://localhost:8000/health
curl http://localhost:7004/health
curl http://localhost:7001/health
curl http://localhost:7002/health
```

After ~30-60 seconds of telemetry flow, runtime AIOps outputs can be queried from API/BFF:

```bash
curl "http://localhost:8000/api/v1/aiops/congestion/latest?limit=20"
curl "http://localhost:8000/api/v1/aiops/sla/latest?limit=20"
curl "http://localhost:8000/api/v1/aiops/slice-classification/latest?limit=20"
curl "http://localhost:8000/api/v1/aiops/events/recent?stream=events.anomaly&count=50"
```

Useful URLs:

- API docs: `http://localhost:8000/docs`
- Grafana: `http://localhost:3000`
- InfluxDB: `http://localhost:8086`

Stop:

```bash
docker compose down
```

Full reset (including persisted data volumes):

```bash
docker compose down -v
```

## 14) API Usage Examples

### Start misrouting scenario

```bash
curl -X POST http://localhost:8000/api/v1/scenarios/start \
  -H "Content-Type: application/json" \
  -d '{"scenario_id":"urllc_misrouting"}'
```

### Inject manual fault

```bash
curl -X POST http://localhost:8000/api/v1/faults/inject \
  -H "Content-Type: application/json" \
  -d '{
    "fault_type":"ran_congestion",
    "affected_entities":["gnb-01","gnb-02"],
    "severity":3,
    "duration_sec":120,
    "kpi_impacts":{"congestion":0.7}
  }'
```

### Pull latest entity KPIs

```bash
curl "http://localhost:8000/api/v1/kpis/latest?domain=ran"
```

### Open SSE stream

```bash
curl -N http://localhost:8000/api/v1/stream/kpis
```

### API contract details (BFF)

| Endpoint | Method | Input | Output |
|---|---|---|---|
| `/health` | GET | none | service status, redis status, timestamp |
| `/config` | GET | none | site/simulation config + static entity list |
| `/api/v1/kpis/latest` | GET | query: `domain`, `siteId`, `sliceId`, `limit` | latest `entity:{id}` snapshots |
| `/api/v1/kpis/recent` | GET | query: `minutes`, `count` | events from `stream:norm.telemetry` |
| `/api/v1/kpis/entity/{entity_id}` | GET | path: `entity_id` | single entity latest state |
| `/api/v1/stream/kpis` | GET | none | SSE stream of canonical telemetry events |
| `/api/v1/aiops/congestion/latest` | GET | query: `limit` | latest runtime congestion outputs from `aiops:congestion:*` |
| `/api/v1/aiops/sla/latest` | GET | query: `limit` | latest runtime SLA outputs from `aiops:sla:*` |
| `/api/v1/aiops/slice-classification/latest` | GET | query: `limit` | latest runtime slice-classification outputs from `aiops:slice_classification:*` |
| `/api/v1/aiops/events/recent` | GET | query: `stream`, `count` | recent runtime output events from AIOps streams |
| `/api/v1/faults/active` | GET | none | proxy response from fault-engine |
| `/api/v1/scenarios/start` | POST | JSON `{ \"scenario_id\": \"...\" }` | scenario start status |
| `/api/v1/scenarios/stop` | POST | none | scenario stop status |
| `/api/v1/faults/inject` | POST | fault payload (`fault_type`, `affected_entities`, `severity`, `duration_sec`, `kpi_impacts`) | injected fault id |
| `/api/v1/export/sla` | GET | none | SLA feature-view JSON |
| `/api/v1/export/slice-classifier` | GET | none | slice-classifier feature-view JSON |
| `/api/v1/export/congestion-sequences` | GET | none | LSTM sequence-style feature-view JSON |

### KPI catalog by entity (emitted telemetry fields)

| Entity | KPI fields |
|---|---|
| `AMF` | `activeUeCount`, `registrationSuccessRate`, `registrationFailureRate`, `registrationRatePps`, `signalingLoadPct`, `pduSessionLatencyMs`, `cpuUtilPct`, `memUtilPct`, `registrationQueueLen` |
| `SMF` | `activeSessions`, `pduSessionSuccessRate`, `pduSetupLatencyMs`, `pduSetupQueueLen`, `cpuUtilPct`, `memUtilPct` |
| `Core UPF` | `dlThroughputGbps`, `ulThroughputGbps`, `activeTunnels`, `queueDepthPct`, `forwardingLatencyMs`, `packetLossPct`, `cpuUtilPct`, `memUtilPct` |
| `Edge UPF` | `dlThroughputGbps`, `ulThroughputGbps`, `activeSessions`, `forwardingLatencyMs`, `packetLossPct`, `localBreakoutRatio`, `cpuUtilPct`, `memUtilPct` |
| `MEC App` | `requestRateRps`, `activeConnections`, `responseTimeMs`, `errorRate`, `throughputMbps`, `cpuUtilPct`, `memUtilPct` |
| `Compute Node` | `cpuUtilPct`, `memUtilPct`, `networkInGbps`, `networkOutGbps`, `runningVnfs`, `saturationScore` |
| `Cell` | `ueCount`, `rbUtilizationPct`, `rsrpDbm`, `rsrqDb`, `sinrDb`, `cqi`, `blerPct`, `handoverSuccessRate`, `rrcSetupSuccessRate`, `handoverAttempts`, `rrcAttempts` |
| `Slice` | `rbUtilizationPct`, `dlThroughputMbps`, `ulThroughputMbps`, `latencyMs`, `packetLossPct`, `ueCount` |

### Fault-engine contract details

| Endpoint | Method | Payload | Purpose |
|---|---|---|---|
| `/scenarios/start` | POST | `{ \"scenario_id\": \"peak_hour\" }` | starts scenario task and injects listed faults |
| `/scenarios/stop` | POST | none | cancels scenario and clears all active faults |
| `/faults/inject` | POST | `fault_type`, `affected_entities`, `severity`, `duration_sec`, `kpi_impacts`, optional `scenario_id` | manual fault activation + timed expiry |
| `/faults/active` | GET | none | returns all currently active faults |
| `/scenarios` | GET | none | available scenario IDs + currently active scenario |

## 15) MLOps Tier (Batch Orchestrator)

Path: `mlops-tier/batch-orchestrator`

This stack is separate from simulation runtime and focuses on:

- dataset preprocessing/validation
- model training with MLflow tracking and model registry
- inference API for 5G/6G predictors
- unit/integration/quality-gate tests

### Data expectations

Raw files expected under `data/raw` (not committed):

- `network_slicing_dataset_enriched_timeseries.csv`
- `train_dataset_enriched_timeseries.csv`
- `5G_prepared.csv`
- `6G_prepared.csv`
- `train_dataset.csv`

### Preprocessing scripts

- `src/data/preprocess_6g.py`
- `src/data/preprocess_congestion_5g.py`
- `src/data/preprocess_sla_5g.py`
- `src/data/preprocess_sla_6g.py`
- `src/data/preprocess_slice_type_5g.py`
- `src/data/preprocess_slice_type_6g.py`

### Validation scripts

- `src/data/validate.py`
- `src/data/validate_congestion_5g.py`
- `src/data/validate_sla_5g.py`
- `src/data/validate_sla_6g.py`
- `src/data/validate_slice_type_5g.py`
- `src/data/validate_slice_type_6g.py`

### Training scripts and registry targets

- `train_congestion_6g.py` -> registered model `congestion-lstm-6g`
- `train_congestion_5g.py` -> local model artifacts (`models/congestion_5g_lstm*.pt`)
- `train_sla_5g.py` -> `sla-xgboost-5g`
- `train_sla_6g.py` -> `sla-xgboost-6g`
- `train_slice_type_5g.py` -> `slice-type-lgbm-5g`
- `train_slice_type_6g.py` -> `slice-type-6g`

### MLflow experiment names and quality gates in code

| Model family | Experiment name | Main metric(s) | Gate in code/tests |
|---|---|---|---|
| Congestion 6G (LSTM) | `congestion-forecast-6g` | `val_mae`, `val_rmse` | `val_mae < 5.0` |
| SLA 5G (XGBoost) | `sla-adherence-5g` | `val_roc_auc`, `val_f1` | `val_roc_auc >= 0.75` |
| SLA 6G (XGBoost) | `sla-adherence-6g` | `val_roc_auc`, `val_f1` | `val_roc_auc >= 0.75` |
| Slice-Type 5G (LightGBM) | `slice-type-5g` | `val_accuracy`, weighted `val_f1` | `val_accuracy >= 0.80` |
| Slice-Type 6G (XGBoost) | `slice-type-6g` | `val_accuracy`, weighted `val_f1` | `val_accuracy >= 0.80` |
| Congestion 5G (LSTM classifier) | `Congestion_Forecasting_5G` | `auc_roc`, `f1`, `recall` | validated by dedicated tests |

### MLOps API endpoints

Service entry: `src/api/main.py`

- `GET /health`
- `POST /predict/congestion_6g`
- `POST /predict/congestion_5g`
- `POST /predict/slice`
- `POST /predict/sla_5g`
- `POST /predict/slice_type_5g`
- `POST /predict/slice_type_6g`
- `POST /predict/sla_6g`

### Local commands (Makefile)

```bash
cd neuroslice-platform/mlops-tier/batch-orchestrator
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

make data
make validate-data
make train-all
make test
make serve
```

### MLOps docker-compose stack

`mlops-tier/batch-orchestrator/docker-compose.yml` starts:

- API container (port `8000`)
- MLflow server (port `5000`)
- Elasticsearch (port `9200`)
- Kibana (port `5601`)

Important: this API also binds `8000`, which conflicts with `api-bff-service` if both stacks run on the same host port.

## 16) Test Coverage

Batch orchestrator test suite (`mlops-tier/batch-orchestrator/tests`) includes:

- FastAPI endpoint tests (`test_api.py`)
- preprocessing and data-shape tests
- data validation script tests
- model forward-pass tests
- MLflow quality-gate tests (`test_model_quality.py`)

Run:

```bash
cd neuroslice-platform/mlops-tier/batch-orchestrator
pytest tests -v
```

## 17) Known Gaps and Practical Notes

- `misrouting-detector` is intentionally deferred from the current AIOps runtime iteration.
- `agentic-ai-tier` remains pending.
- `control-tier` remains pending.
- `infrastructure/k8s` and `infrastructure/istio` remain pending because Scenario B focuses on Docker Compose.
- Adapter services expose Prometheus-format `/metrics`, but no Prometheus service is currently deployed in compose.
- Default credentials/tokens in compose are development-friendly defaults and should be replaced for non-local environments.

## 18) Repository Map (Current State)

```text
neuroslice-platform/
├── infrastructure/
│   ├── docker-compose.yml
│   ├── .env.example
│   └── observability/
│       └── grafana/provisioning/...
├── simulation-tier/
│   ├── simulator-core/
│   ├── simulator-edge/
│   ├── simulator-ran/
│   ├── fault-engine/
│   ├── scenarios/
│   └── README.md
├── ingestion-tier/
│   ├── shared/
│   ├── adapter-ves/
│   ├── adapter-netconf/
│   ├── normalizer/
│   └── telemetry-exporter/
├── aiops-tier/
│   ├── congestion-detector/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── consumer.py
│   │   ├── inference.py
│   │   ├── model_loader.py
│   │   ├── publisher.py
│   │   ├── schemas.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── slice-classifier/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── consumer.py
│   │   ├── inference.py
│   │   ├── model_loader.py
│   │   ├── publisher.py
│   │   ├── schemas.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── sla-assurance/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── consumer.py
│   │   ├── inference.py
│   │   ├── model_loader.py
│   │   ├── publisher.py
│   │   ├── schemas.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── misrouting-detector/     (deferred / not implemented)
├── api-dashboard-tier/
│   ├── api-bff-service/
│   ├── auth-service/
│   ├── dashboard-backend/
│   ├── kong-gateway/
│   └── react-dashboard/
├── mlops-tier/
│   └── batch-orchestrator/
├── control-tier/                (placeholder)
└── agentic-ai-tier/             (placeholder)
```

---

If you are onboarding a new contributor, the fastest path is:

1. Run `infrastructure/docker-compose.yml`.
2. Validate API + Grafana + scenario injection.
3. Then move to `mlops-tier/batch-orchestrator` for model training and prediction API workflows.
