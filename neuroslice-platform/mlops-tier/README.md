# MLOps Tier

The MLOps tier owns NeuroSlice offline preprocessing, training, validation, model lifecycle metadata, and the prediction API. The active project in this repository is `batch-orchestrator/`.

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

The current lifecycle is:

1. preprocess and validate data
2. train models
3. export ONNX FP16 artifacts when available
4. persist metadata to MLflow
5. write lifecycle records to `batch-orchestrator/models/registry.json`
6. let runtime AIOps services discover local promoted artifacts through read-only mounts

Important note for this workspace: `models/registry.json` currently contains no promoted entries, so runtime AIOps services still rely on their local fallback artifact paths.

## Development Notes

- Host-side dependencies are pinned broadly enough for modern Python 3.13 environments.
- The Docker image for `batch-orchestrator` still runs on `python:3.10-slim`.
- Do not run the standalone MLOps compose file and the integrated `mlops` profile at the same time unless you intentionally remap ports.

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
