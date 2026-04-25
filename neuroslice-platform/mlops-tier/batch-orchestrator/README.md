# Batch Orchestrator

`batch-orchestrator` is the active MLOps project for NeuroSlice. It contains the offline data pipeline, model training code, lifecycle metadata generation, prediction API, tests, notebooks, and generated reports used by the rest of the platform.

## Project Scope

This project currently owns:

- data preprocessing and validation
- model training for congestion, SLA, and slice-type tasks
- lifecycle metadata and registry generation
- ONNX FP16 export when supported
- FastAPI prediction service
- automated tests and model report generation

## Operating Modes

Host mode:

```bash
cd neuroslice-platform/mlops-tier/batch-orchestrator
pip install -r requirements.txt
make pipeline
```

Standalone Docker mode:

```bash
cd neuroslice-platform/mlops-tier/batch-orchestrator
docker compose up --build
```

Integrated platform mode:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops up --build
```

Manual offline worker against the integrated services:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops --profile mlops-worker run --rm mlops-worker
```

This worker runs the production-like 5G lifecycle path:

1. `congestion_5g` preprocessing, validation, training, MLflow logging, ONNX/FP16 export, and registry promotion
2. the same lifecycle pattern for `sla_5g`
3. the same lifecycle pattern for `slice_type_5g`
4. model report generation from `models/registry.json`

## Common Commands

```bash
make data
make validate-data
make train-all
make pipeline-congestion-5g
make model-report
make test
make serve
make pipeline
```

Useful task-specific targets:

- `make data-sla-5g`
- `make data-sla-6g`
- `make data-congestion-5g`
- `make data-slice-type-5g`
- `make data-slice-type-6g`
- `make train-sla-5g`
- `make train-sla-6g`
- `make train-congestion-5g`
- `make train-congestion-6g`
- `make train-slice-type-5g`
- `make train-slice-type-6g`

## Project Layout

- `src/data/`: preprocessing and validation scripts
- `src/models/`: training and lifecycle logic
- `src/api/`: prediction API
- `src/reports/`: training report generation
- `tests/`: API, preprocessing, lifecycle, and quality tests
- `notebooks/`: exploratory and modeling notebooks
- `data/raw/`: committed source datasets
- `data/processed/`: generated preprocessing outputs when data targets are run
- `models/registry.json`: tracked lifecycle registry metadata
- `models/`: generated runtime artifacts when training/export targets are run
- `reports/`: generated Markdown summaries
- `report/`: project PDF report asset

## MLflow, MinIO, and Registry Contract

The integrated stack uses:

- MLflow experiment: `neuroslice-aiops`
- MLflow tracking URI in Compose: `http://mlflow-server:5000`
- MLflow backend store: `mlops-postgres`
- MLflow default artifact root: `s3://mlflow-artifacts`
- MinIO endpoint in Compose: `http://minio:9000`
- MinIO bucket: `mlflow-artifacts`

Training scripts log parameters, metrics, model binaries, preprocessors/scalers/encoders, ONNX artifacts, and ONNX FP16 artifacts when conversion succeeds. If ONNX export fails, the run records `reports/onnx_export_status.json` and registry fields `onnx_export_status` and `onnx_export_reason`, but the training run can still complete.

Every successful training run appends a record to `models/registry.json`. Required production fields include:

- `model_name`, `task_type`, `version`, `stage`, `promoted`, `format`
- `artifact_uri`, `onnx_uri`, `onnx_fp16_uri`, `preprocessor_uri`
- `mlflow_run_id`, `experiment_name`, `metrics`, `quality_gate_status`
- `input_schema`, `created_at`

Only quality-gate-passing models are eligible for promotion. The registry keeps old metadata and marks the best valid version for each model as `promoted=true` and `stage=production`. `format=onnx_fp16` is preferred when the FP16 artifact exists.

## Prediction API

The FastAPI app in `src/api/main.py` exposes:

- `GET /health`
- `POST /predict/congestion_6g`
- `POST /predict/congestion_5g`
- `POST /predict/slice`
- `POST /predict/sla_5g`
- `POST /predict/slice_type_5g`
- `POST /predict/slice_type_6g`
- `POST /predict/sla_6g`

Default published URL:

- `http://localhost:8010`

## Current Repository State

Tracked inputs and metadata in this workspace:

- raw CSV datasets under `data/raw/`
- `models/registry.json`
- `reports/model_training_summary.md`
- `report/Rapport_PI_modeling_phase.pdf`

Important current notes:

- `models/registry.json` is no longer empty
- new training runs append schema-compatible entries and keep historical metadata
- runtime AIOps services read promoted production entries from the registry
- generated local model binaries and ONNX files are ignored by git; MinIO is the artifact store for integrated MLOps

Generated artifacts such as `data/processed/*.pkl`, `data/processed/*.npz`, `models/*.pt`, `models/*.pth`, `models/*.pkl`, `models/*.onnx`, and `models/onnx/` are intentionally gitignored and may be absent in a fresh clone.

## Docker Notes

- the Docker image uses `python:3.10-slim`
- the standalone Compose file starts `api`, `mlops-postgres`, `minio`, `minio-init`, `mlflow-server`, `elasticsearch`, `logstash`, and `kibana`
- do not run the standalone Compose file and the integrated `mlops` profile at the same time unless you change ports

## Integrated Verification

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops up --build
docker compose --profile mlops --profile mlops-worker run --rm mlops-worker
```

Verify:

- MLflow UI: `http://localhost:5000`
- MinIO console: `http://localhost:9001`
- MLOps API: `http://localhost:8010`
- `models/registry.json` contains at least one `promoted=true`, `stage=production` model entry

## Reports and Tests

Generate the training summary:

```bash
make model-report
```

Run the test suite:

```bash
pytest tests -v
```

The existing tests cover the API, preprocessing, validation, export helpers, model lifecycle registry logic, and quality gates.
