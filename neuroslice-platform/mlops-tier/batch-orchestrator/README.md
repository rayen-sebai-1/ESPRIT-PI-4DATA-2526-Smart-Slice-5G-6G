# Batch Orchestrator

`batch-orchestrator` is the active MLOps project for NeuroSlice. It contains the offline data pipeline, model training code, lifecycle metadata generation, prediction API, tests, and notebooks used by the rest of the platform.

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

## Common Commands

```bash
make data
make validate-data
make train-all
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
- `data/processed/`: generated processed datasets and preprocessing artifacts
- `models/`: runtime model artifacts and `registry.json`
- `reports/`: generated Markdown reports

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

## Current Artifacts in This Workspace

Committed model files:

- `models/congestion_5g_lstm.pth`
- `models/congestion_5g_lstm_traced.pt`

Committed processed artifacts include:

- `data/processed/preprocessor_congestion_5g.pkl`
- `data/processed/scaler_sla_5g.pkl`
- `data/processed/scaler_sla_6g.pkl`
- `data/processed/label_encoder_slice_type_5g.pkl`
- `data/processed/label_encoder_slice_type_6g.pkl`
- processed `.npz` and `.csv` datasets

Current registry status:

- `models/registry.json` exists
- it currently contains no promoted entries

That means the integrated runtime still depends on fallback local artifact paths for several AIOps services.

## Docker Notes

- the Docker image uses `python:3.10-slim`
- the standalone compose file starts `api`, `postgres`, `minio`, `minio-init`, `mlflow`, `elasticsearch`, `logstash`, and `kibana`
- do not run the standalone compose file and the integrated `mlops` profile at the same time unless you change ports

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
