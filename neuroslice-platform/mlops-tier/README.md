# MLOps Tier

Offline data engineering, model training, registry tracking, and prediction API for Smart Slice 5G/6G models.

## Tier Purpose

This tier manages the model lifecycle used by runtime AIOps services:

- Data preprocessing and validation.
- Training pipelines for congestion, SLA, and slice-type tasks (5G/6G).
- Local MLflow tracking and model registry metadata.
- Serving API for direct prediction calls.
- Testing and quality gates for data/model logic.

## Current Scope

Active subproject:

- `batch-orchestrator/`

It contains:

- `src/data/` preprocessing + validation pipelines.
- `src/models/` training scripts by model family and generation.
- `src/api/` FastAPI inference service.
- `tests/` data/model/API tests.
- `mlflow.db` + `mlruns/` local tracking artifacts.
- `models/` exported/traced model artifacts used by runtime AIOps.
- `data/` raw and processed datasets.

## API Endpoints

Prediction API entrypoint: `src/api/main.py`

Endpoints:

- `GET /health`
- `POST /predict/congestion_6g`
- `POST /predict/congestion_5g`
- `POST /predict/slice`
- `POST /predict/sla_5g`
- `POST /predict/slice_type_5g`
- `POST /predict/slice_type_6g`
- `POST /predict/sla_6g`

Model loading behavior:

- Loads from MLflow URIs and/or local model files.
- Some endpoints return `503` if required model/scaler/encoder is unavailable.

## Useful Make Targets

From `batch-orchestrator/Makefile`:

- `make setup`
- `make data-sla-5g`, `make data-congestion-5g`, `make data-slice-type-5g`, `make data-slice-type-6g`
- `make validate-data-sla-5g`, `make validate-data-congestion-5g`, `make validate-data-slice-type-5g`
- `make train-sla-5g`, `make train-congestion-5g`, `make train-slice-type-5g` (and 6G variants)
- `make train-all`
- `make test`
- `make mlflow-ui`
- `make serve`
- `make pipeline`

## Run Locally

```bash
cd neuroslice-platform/mlops-tier/batch-orchestrator
pip install -r requirements.txt
make serve
```

MLflow UI:

```bash
cd neuroslice-platform/mlops-tier/batch-orchestrator
make mlflow-ui
```

## Runtime Integration with AIOps Tier

The infrastructure compose mounts this project into AIOps services:

- host path: `../mlops-tier/batch-orchestrator`
- container path: `/mlops`

This is how runtime services access:

- traced model files in `/mlops/models`
- preprocessors/scalers/encoders in `/mlops/data/processed`
- MLflow metadata in `/mlops/mlflow.db` and `/mlops/mlruns`

## Folder Map

```text
mlops-tier/
└── batch-orchestrator/
    ├── src/
    ├── tests/
    ├── data/
    ├── models/
    ├── mlruns/
    ├── notebooks/
    ├── Makefile
    └── MLproject
```
