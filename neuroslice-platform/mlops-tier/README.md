# MLOps Tier

The MLOps tier owns the offline model lifecycle for NeuroSlice. The active subproject is `batch-orchestrator/`.

## What Changed

The offline pipeline now supports a production-like Scenario B flow:

- training
- evaluation
- ONNX export
- FP16 conversion
- MLflow tracking metadata in PostgreSQL
- MLflow artifacts in MinIO
- promoted-model metadata in `models/registry.json`
- markdown reporting in `reports/model_training_summary.md`

Local development still works without Docker. When `MLFLOW_TRACKING_URI` is unset, training falls back to the local SQLite store at `mlflow.db`.

## Key Artifacts

- `batch-orchestrator/models/registry.json`
- `batch-orchestrator/models/onnx/`
- `batch-orchestrator/reports/model_training_summary.md`
- `batch-orchestrator/.env.example`
- `batch-orchestrator/docker-compose.yml`

## Common Commands

```bash
cd neuroslice-platform/mlops-tier/batch-orchestrator
pip install -r requirements.txt
make pipeline
make model-report
```

Integrated Docker runtime:

```bash
cd neuroslice-platform/infrastructure
docker compose up --build mlflow-postgres minio minio-init mlflow mlops-api elasticsearch logstash kibana
```

## Integration Point

The AIOps services consume the offline outputs through the mounted `/mlops` directory and the shared registry metadata. Promoted ONNX FP16 artifacts are preferred, with legacy model loading left in place as fallback.

See [batch-orchestrator/README.md](./batch-orchestrator/README.md) for the Scenario B details and promotion rules.
