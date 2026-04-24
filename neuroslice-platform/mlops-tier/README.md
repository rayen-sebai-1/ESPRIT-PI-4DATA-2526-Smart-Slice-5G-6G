# MLOps Tier

The MLOps tier contains the offline data-preparation, training, testing, and prediction-serving project used by the runtime AIOps services.

## Current Scope

The only committed subproject in this tier is:

- `batch-orchestrator/`

## What Exists In `batch-orchestrator`

Committed source and assets:

- `src/data/` preprocessing and validation scripts
- `src/models/` training scripts
- `src/api/` FastAPI prediction API
- `tests/` pytest suite
- `data/raw/` committed raw datasets
- `notebooks/` modeling notebooks
- `report/` project report artifact
- `Makefile`
- `MLproject`
- `Dockerfile`
- `docker-compose.yml`

Not currently committed in this workspace:

- `models/`
- `data/processed/`
- `mlflow.db`
- `mlruns/`

Those missing directories matter because parts of the API, the local Dockerfile, and the runtime AIOps services expect generated artifacts to exist there.

## Prediction API

Entrypoint:

- `batch-orchestrator/src/api/main.py`

Current routes:

- `GET /health`
- `POST /predict/congestion_6g`
- `POST /predict/congestion_5g`
- `POST /predict/slice`
- `POST /predict/sla_5g`
- `POST /predict/slice_type_5g`
- `POST /predict/slice_type_6g`
- `POST /predict/sla_6g`

Model-loading behavior:

- loads MLflow-registered models when available
- loads local TorchScript and joblib artifacts when present
- some endpoints intentionally return `503` when required trained artifacts are missing
- `/predict/slice` uses a stub path when the slice-selection model is not available

## Training And Data Scripts

Current training scripts in `src/models/`:

- `train_congestion_5g.py`
- `train_congestion_6g.py`
- `train_sla_5g.py`
- `train_sla_6g.py`
- `train_slice_type_5g.py`
- `train_slice_type_6g.py`

Current preprocessing and validation scripts in `src/data/`:

- `preprocess_6g.py`
- `preprocess_congestion_5g.py`
- `preprocess_sla_5g.py`
- `preprocess_sla_6g.py`
- `preprocess_slice_type_5g.py`
- `preprocess_slice_type_6g.py`
- `validate.py`
- `validate_congestion_5g.py`
- `validate_sla_5g.py`
- `validate_sla_6g.py`
- `validate_slice_type_5g.py`
- `validate_slice_type_6g.py`

## Useful Make Targets

From `batch-orchestrator/Makefile`:

- `make setup`
- `make lint`
- `make format`
- `make security`
- `make quality`
- `make data`
- `make data-sla-5g`
- `make data-sla-6g`
- `make data-congestion-5g`
- `make data-slice-type-5g`
- `make data-slice-type-6g`
- `make validate-data`
- `make validate-data-sla-5g`
- `make validate-data-sla-6g`
- `make validate-data-congestion-5g`
- `make validate-data-slice-type-5g`
- `make validate-data-slice-type-6g`
- `make train-sla-5g`
- `make train-sla-6g`
- `make train-congestion-5g`
- `make train-congestion-6g`
- `make train-slice-type-5g`
- `make train-slice-type-6g`
- `make train-all`
- `make test`
- `make mlflow-ui`
- `make serve`
- `make docker-build`
- `make docker-run`
- `make docker-compose-up`
- `make pipeline`

## Runtime Integration With AIOps

The main platform Compose file mounts this project into the online AIOps workers as:

- host path: `../mlops-tier/batch-orchestrator`
- container path: `/mlops`

The runtime AIOps workers expect generated artifacts such as:

- `/mlops/models/...`
- `/mlops/data/processed/...`
- `/mlops/mlflow.db`
- `/mlops/mlruns/...`

If those artifacts are absent, the workers stay up but fall back to heuristic behavior where supported.

## Local Usage

Run the API from source:

```bash
cd neuroslice-platform/mlops-tier/batch-orchestrator
pip install -r requirements.txt
make serve
```

Run the MLflow UI from source:

```bash
cd neuroslice-platform/mlops-tier/batch-orchestrator
make mlflow-ui
```

## Current Repository Caveat

The committed `Dockerfile` copies `models/` and `mlruns/`, but those directories are not present in the current workspace. A clean Docker build from this snapshot will therefore require generated artifacts or Dockerfile adjustments before it succeeds.

## Folder Map

```text
mlops-tier/
|-- README.md
`-- batch-orchestrator/
    |-- Dockerfile
    |-- Makefile
    |-- MLproject
    |-- docker-compose.yml
    |-- requirements.txt
    |-- data/
    |   `-- raw/
    |-- notebooks/
    |-- report/
    |-- src/
    `-- tests/
```
