# MLOps Tier

The MLOps tier owns NeuroSlice offline preprocessing, training, validation, lifecycle metadata, and the prediction API. The active project in this repository is `batch-orchestrator/`.

## Supported Modes

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

## Services in the Integrated `mlops` Profile

- `mlops-postgres`
- `minio`
- `minio-init`
- `mlflow-server`
- `elasticsearch`
- `logstash`
- `mlops-api`

Published URLs:

- MLflow UI: `http://localhost:5000`
- MinIO API: `http://localhost:9000`
- MinIO console: `http://localhost:9001`
- MLOps API: `http://localhost:8010`

## Artifact Flow

Production-like ownership is split deliberately:

- platform `postgres`: auth-service and dashboard-backend only
- `mlops-postgres`: MLflow backend metadata only
- MinIO bucket `mlflow-artifacts`: model binaries, ONNX, ONNX FP16, preprocessors, scalers, encoders, reports, and MLflow run artifacts

The current lifecycle is:

1. preprocess and validate data
2. train models in the shared MLflow experiment `neuroslice-aiops`
3. log parameters, metrics, model artifacts, and preprocessing artifacts to MLflow/MinIO
4. export ONNX and ONNX FP16 artifacts when conversion succeeds
5. record ONNX export failures in MLflow without failing the whole training run
6. append lifecycle records to `batch-orchestrator/models/registry.json`
7. promote only quality-gate-passing models and mark the best promoted version as `stage=production`
8. let runtime AIOps services discover promoted artifacts through the registry, preferring ONNX FP16, then ONNX, then local model fallbacks, then heuristics

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
- `batch-orchestrator/models/registry.json` contains a `promoted=true`, `stage=production` entry
- AIOps services can read the production entry and prefer `onnx_fp16_uri`/`onnx_fp16_path` when present

## Development Notes

- The Docker image for `batch-orchestrator` runs on `python:3.10-slim`.
- The standalone batch-orchestrator Compose file includes Kibana, while the integrated platform `mlops` profile does not.
- Do not run the standalone MLOps Compose file and the integrated `mlops` profile at the same time unless you intentionally remap ports.

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

Project details, API routes, generated outputs, and dataset layout are documented in `batch-orchestrator/README.md`.
