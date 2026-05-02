# MLOps Tier

Last verified: 2026-04-30.

The MLOps tier owns NeuroSlice offline preprocessing, training, MLflow tracking, model registry metadata, ONNX export, FP16 conversion, promotion, and the prediction API. The active project is `batch-orchestrator/`.

## Scenario B Drift References

When the MLOps pipeline promotes a model (`promote_onnx_artifacts`), it now also generates drift reference artifacts alongside each promoted model:

```
models/promoted/{model_name}/current/drift_reference.npz
models/promoted/{model_name}/current/drift_feature_schema.json
```

These are loaded by the `aiops-drift-monitor` service (optional `drift` profile, Alibi MMD). If they are absent, the detector reports `reference_missing` and continues in degraded mode.

To generate them without running the full pipeline:

```bash
cd neuroslice-platform/mlops-tier/batch-orchestrator
python -m src.mlops.drift_reference models/promoted data/processed
```

## Runtime Modes

Integrated platform mode:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops up --build
```

Standalone MLOps-only mode:

```bash
cd neuroslice-platform/mlops-tier/batch-orchestrator
docker compose up --build
```

Manual offline pipeline against the integrated stack:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops --profile mlops-worker run --rm mlops-worker
```

## Integrated `mlops` Services

- `mlops-postgres`: MLflow backend metadata
- `minio`: S3-compatible artifact storage
- `minio-init`: creates the artifact bucket
- `mlflow-server`: tracking UI and registry API
- `elasticsearch`: prediction/log analytics backend for MLOps logging
- `logstash`: prediction log ingestion
- `kibana`: Elasticsearch UI for prediction/log inspection
- `mlops-api`: FastAPI prediction and health API

Published URLs:

- MLflow UI: `http://localhost:5000`
- MinIO API: `http://localhost:9000`
- MinIO console: `http://localhost:9001`
- MLOps API: `http://localhost:8010`
- Elasticsearch: `http://localhost:9200`
- Kibana: `http://localhost:5601`

In the integrated profile, Logstash listens inside Docker Compose at `http://logstash:8081/predictions`; it is not published on the host.

## Model Lifecycle

The current lifecycle is:

1. preprocess and validate data
2. train PyTorch, XGBoost, or LightGBM models
3. log params, metrics, model artifacts, and preprocessing artifacts to MLflow/MinIO
4. register the model in MLflow when the training script has a registered model name
5. export `model.onnx`
6. convert ONNX to `model_fp16.onnx` with `onnxconverter-common`
7. validate ONNX and FP16 ONNX, including ONNX Runtime session load
8. append lifecycle metadata to `batch-orchestrator/models/registry.json`
9. promote quality-gate-passing models into `models/promoted/{model_name}/{version}/`
10. update `models/promoted/{model_name}/current/` as the production pointer
11. AIOps services load `current/model_fp16.onnx` and hot reload on metadata changes

## Promotion Layout

```text
models/promoted/{model_name}/{version}/model.onnx
models/promoted/{model_name}/{version}/model_fp16.onnx
models/promoted/{model_name}/{version}/metadata.json
models/promoted/{model_name}/current/model.onnx
models/promoted/{model_name}/current/model_fp16.onnx
models/promoted/{model_name}/current/metadata.json
models/promoted/{model_name}/current/version.txt
models/promoted/{model_name}/current/drift_reference.npz
models/promoted/{model_name}/current/drift_feature_schema.json
```

Production metadata includes:

- `model_name`: MLflow registered model name when available, otherwise deployment name
- `deployment_name`: runtime deployment key such as `sla_5g`
- `version`: MLflow model version when available, otherwise local registry version
- `run_id`
- `updated_at`
- `created_at`
- `metrics`
- `framework`: `pytorch`, `xgboost`, or `lightgbm`

## Runtime Consumers

AIOps services mount generated models from the batch orchestrator as read-only paths:

- `/mlops/models`
- `/mlops/data`
- `/mlops/src`

`dashboard-backend` mounts `mlops-tier/batch-orchestrator/models` read-only at `/mlops/models` and exposes the MLOps Control Center under `/api/dashboard/mlops/*` (see `api-dashboard-tier/README.md`). The dashboard backend reads `registry.json` and `promoted/*/current/metadata.json` directly, queries Elasticsearch for prediction monitoring, and delegates `promote` / `rollback` calls to `mlops-api` at `MLOPS_API_BASE_URL`. The browser never talks to MLflow, MinIO, Elasticsearch, or the filesystem directly.

## MLOps Runner

`mlops-tier/mlops-runner/` is an internal-only worker that exists so the React dashboard can trigger the offline MLOps pipeline without giving any other service direct access to the Docker socket or arbitrary shell commands. See `mlops-runner/README.md` for the full security model.

- It accepts `POST /run-action` and `GET /health`.
- Actions are mapped via a fixed `_ACTION_MAP` (e.g. `full_pipeline` → `make mlops-full`); callers cannot inject arbitrary shell strings.
- It is not published on the host — only `dashboard-backend` and `mlops-drift-monitor` reach it via the internal Compose network.
- A kill switch `MLOPS_ORCHESTRATION_ENABLED=false` in `mlops-runner` immediately disables command execution.
- An optional shared bearer token `MLOPS_RUNNER_TOKEN` blocks all other callers.
- Each request carries a `trigger_source` field (`manual` | `drift` | `scheduled`) that is logged and returned in the response.

Trigger flow from the dashboard:

```text
React (/mlops/operations) -> Kong /api/dashboard/mlops/pipeline/run
  -> dashboard-backend POST /mlops/pipeline/run
    -> create dashboard.mlops_pipeline_runs row (RUNNING)
    -> background task -> mlops-runner POST /run-action {action: "full_pipeline", trigger_source: "manual"}
      -> docker exec <mlops-api-container> make mlops-full
    -> capture stdout/stderr -> redact -> persist on the row
```

Trigger flow from drift detection:

```text
mlops-drift-monitor (mlops-tier) detects anomaly burst
  -> mlops-runner POST /run-action {action: "full_pipeline", trigger_source: "drift"}
    -> docker exec <mlops-api-container> make mlops-full
```

## mlops-drift-monitor

`mlops-tier/drift-monitor/` (service name `mlops-drift-monitor`) is a lightweight FastAPI service that watches the `events.anomaly` Redis stream and automatically triggers the MLOps pipeline when anomaly bursts exceed a configurable threshold.

- Polls `events.anomaly` Redis stream every `DRIFT_POLL_INTERVAL_SECONDS` seconds (default: 30).
- Counts anomaly events within a sliding `DRIFT_WINDOW_SECONDS` window (default: 120 s).
- Triggers `mlops-runner POST /run-action` when count ≥ `DRIFT_ANOMALY_THRESHOLD` (default: 5).
- Enforces a `DRIFT_COOLDOWN_SECONDS` window (default: 600 s) between consecutive triggers.
- Publishes drift events to the `events.drift` Redis stream and persists status in Redis keys `drift:status` and `drift:events`.
- Reads runtime flag keys under `runtime:service:mlops-drift-monitor:*`; when disabled, trigger attempts are skipped.
- Part of the default Compose runtime (no separate profile required). Internal only — no published host port.

This monitor is distinct from `aiops-tier/drift-monitor`:
- `mlops-drift-monitor` (this section): anomaly-count trigger for retraining orchestration.
- `aiops-drift-monitor` (`drift` profile): Alibi Detect MMD statistical detector using `drift_reference.npz` and `drift_feature_schema.json`.

## Environment Variables Clarification

- `MLOPS_PIPELINE_ENABLED`: dashboard/drift trigger gate. It controls whether `dashboard-backend` and `mlops-drift-monitor` attempt to trigger a pipeline run.
- `MLOPS_ORCHESTRATION_ENABLED`: runner execution gate. It controls whether `mlops-runner` executes any mapped action after receiving a trigger.
- In Scenario B, both should be `true` to allow end-to-end pipeline execution from UI or drift trigger.

Endpoints:

- `GET /health`
- `GET /drift/status`
- `GET /drift/events`
- `POST /drift/trigger` (manual test trigger)

Dashboard evaluation endpoints:

- `GET /api/dashboard/mlops/evaluation`
- `GET /api/dashboard/mlops/evaluation/{model_name}`

These read Scenario B pseudo-ground-truth metrics generated by `aiops-tier/online-evaluator`.

Primary production model paths:

- `/mlops/models/promoted/congestion_5g/current/model_fp16.onnx`
- `/mlops/models/promoted/sla_5g/current/model_fp16.onnx`
- `/mlops/models/promoted/slice_type_5g/current/model_fp16.onnx`

## Verification

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops up --build
docker compose --profile mlops --profile mlops-worker run --rm mlops-worker
```

Then verify:

- MLflow UI at `http://localhost:5000` shows runs under `neuroslice-aiops`
- MinIO console at `http://localhost:9001` contains bucket `mlflow-artifacts`
- MLOps API health responds at `http://localhost:8010/health`
- `batch-orchestrator/models/promoted/{model_name}/current/model_fp16.onnx` exists for promoted models
- `metadata.json` version changes after a newer promotion
- AIOps service logs show hot reload messages after a promoted-current update

## Development Notes

- The Docker image for `batch-orchestrator` runs on `python:3.10-slim`.
- The host requirements file also supports local Python development.
- Both the standalone batch-orchestrator Compose file and the integrated platform `mlops` profile include Kibana.
- Do not run standalone MLOps Compose and the integrated `mlops` profile together unless you intentionally remap ports.
- Generated artifacts under `models/`, `data/processed/`, and `reports/model_training_summary.md` are runtime outputs.

## CI/CD

The pipeline is defined in `.github/workflows/mlops-ci.yml` and runs on every push and pull request.

### Stages

| # | Stage | Tool | Notes |
|---|-------|------|-------|
| 1 | Checkout | `actions/checkout@v4` | |
| 2 | Python setup | `actions/setup-python@v5` | Python 3.10, pip cache enabled |
| 3 | Install dependencies | pip | CPU-only PyTorch in CI to avoid 2 GB+ CUDA download |
| 4 | Format check | `black --check` | Fails on diff; never auto-formats |
| 5 | Linting | `ruff check` | |
| 6 | Tests | `pytest -v` | Integration-heavy tests ignored; mocked API tests run |
| 7 | Docker build | `docker build` | Image tagged `mlops-fastapi:ci`; CPU torch via `--build-arg PYTORCH_INDEX=cpu` |
| 8 | Docker push | `docker push` | Only on push to `main`; skipped when `DOCKER_USERNAME` secret is unset |

### Docker push secrets

To enable image push, add these repository secrets in **Settings → Secrets → Actions**:

| Secret | Value |
|--------|-------|
| `DOCKER_USERNAME` | Registry username |
| `DOCKER_PASSWORD` | Registry password or access token |
| `DOCKER_REGISTRY` | Registry host (defaults to `docker.io`) |

If `DOCKER_USERNAME` is absent the push step prints a notice and exits cleanly.

### Running the checks locally

```bash
cd neuroslice-platform/mlops-tier/batch-orchestrator
black --check src/ tests/
ruff check src/ tests/
pytest tests/ -v \
  --ignore=tests/test_model_lifecycle_registry.py \
  --ignore=tests/test_model_quality.py \
  --ignore=tests/test_model_report.py
```

## Common Commands

```bash
cd neuroslice-platform/mlops-tier/batch-orchestrator
pip install -r requirements.txt
make data
make validate-data
make train-all
make model-report
make test
make serve
```

Project details are documented in `batch-orchestrator/README.md`.
