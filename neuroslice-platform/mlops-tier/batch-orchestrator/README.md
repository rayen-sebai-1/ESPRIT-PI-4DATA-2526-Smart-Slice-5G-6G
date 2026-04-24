# Batch Orchestrator

The batch orchestrator keeps all Scenario B MLOps source code in one place:

- offline preprocessing and validation
- model training and reporting
- ONNX FP16 export
- registry metadata generation
- FastAPI prediction service

The authoritative integrated runtime now lives in `neuroslice-platform/infrastructure/docker-compose.yml`. The local `docker-compose.yml` in this folder remains available as standalone developer mode.

## Operating Modes

Local fallback mode on the host:

- unset `MLFLOW_TRACKING_URI` to use `sqlite:///mlflow.db`
- run `make pipeline` directly from this folder

Integrated Scenario B mode:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops up --build
```

Standalone MLOps-only mode:

```bash
cd neuroslice-platform/mlops-tier/batch-orchestrator
docker compose up --build
```

## Runtime Access

When the integrated profile is running:

- MLflow UI: `http://localhost:5000`
- MinIO console: `http://localhost:9001`
- MLOps API: `http://localhost:8010`

The integrated API is published as `mlops-api` and is built from this directory without moving the source code.

## Manual Pipeline Execution

Run on the host:

```bash
cd neuroslice-platform/mlops-tier/batch-orchestrator
pip install -r requirements.txt
make pipeline
```

Run with the integrated Docker services:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops --profile mlops-worker run --rm mlops-worker
```

`mlops-worker` is intentionally manual and does not start during `docker compose --profile mlops up --build`.

## Generated Outputs

Important outputs remain local to this project directory:

- `models/registry.json`
- `models/onnx/*.onnx`
- `reports/model_training_summary.md`
- `data/processed/*`

Those paths are mounted into the integrated services so Docker usage and non-Docker usage share the same artifacts.

## Artifact Flow

The expected flow is:

1. training
2. ONNX FP16 export
3. MLflow metadata in PostgreSQL
4. artifacts in MinIO
5. promoted registry metadata in `models/registry.json`
6. AIOps runtime discovery and future hot reload

## Standalone Compose Notes

`docker-compose.yml` in this folder is kept as an isolated MLOps developer stack. It is useful for focused MLOps work, but the infrastructure compose file is the canonical integrated Scenario B path for the full platform.
