# MLOps Tier

The MLOps tier owns NeuroSlice offline model training, evaluation, promotion metadata, and the Scenario B API surface. The active project is `batch-orchestrator/`.

## Supported Modes

Integrated Scenario B mode is now driven from the infrastructure compose file:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops up --build
```

The standalone MLOps-only compose file is still available for isolated developer work:

```bash
cd neuroslice-platform/mlops-tier/batch-orchestrator
docker compose up --build
```

Do not run both stacks at the same time unless you intentionally change the published host ports.

## Common Commands

Offline pipeline on the host:

```bash
cd neuroslice-platform/mlops-tier/batch-orchestrator
pip install -r requirements.txt
make pipeline
make model-report
```

Offline pipeline through the integrated Docker stack:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops --profile mlops-worker run --rm mlops-worker
```

## Scenario B Services

The integrated profile wires these services into the shared platform network:

- `mlops-postgres`
- `minio`
- `minio-init`
- `mlflow-server`
- `elasticsearch`
- `logstash`
- `mlops-api`

Access points:

- MLflow UI: `http://localhost:5000`
- MinIO console: `http://localhost:9001`
- MLOps API: `http://localhost:8010`

## Artifact Flow

The Scenario B lifecycle is:

1. training
2. evaluation and promotion checks
3. ONNX FP16 export
4. MLflow metadata persisted in PostgreSQL
5. artifacts written to MinIO
6. registry metadata written to `batch-orchestrator/models/registry.json`
7. AIOps workers consume the promoted local artifacts through read-only mounts

See [batch-orchestrator/README.md](./batch-orchestrator/README.md) for the project-level details.
