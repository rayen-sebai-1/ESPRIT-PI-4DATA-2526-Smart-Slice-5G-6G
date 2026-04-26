# MLOps Tier

The MLOps tier owns NeuroSlice offline preprocessing, training, MLflow tracking, model registry metadata, ONNX export, FP16 conversion, promotion, and the prediction API. The active project is `batch-orchestrator/`.

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
- `mlops-api`: FastAPI prediction and health API

Published URLs:

- MLflow UI: `http://localhost:5000`
- MinIO API: `http://localhost:9000`
- MinIO console: `http://localhost:9001`
- MLOps API: `http://localhost:8010`

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
- The standalone batch-orchestrator Compose file includes Kibana, while the integrated platform `mlops` profile does not.
- Do not run standalone MLOps Compose and the integrated `mlops` profile together unless you intentionally remap ports.
- Generated artifacts under `models/`, `data/processed/`, and `reports/model_training_summary.md` are runtime outputs.

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
