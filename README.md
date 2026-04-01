# Smart Slice Selection in 5G/6G Networks – MLOps Pipeline

> **Project:** ESPRIT · Azerty67 · 4th Year DATA · 2025/2026  
> **Notebook operationalised:** `notebooks/network_slicing_congestion_LSTM.ipynb`

---

## Overview

This repository applies an end-to-end **MLOps** pipeline to a congestion-forecasting LSTM for 6G network slicing.  
The pipeline covers data preprocessing, experiment tracking with **MLflow**, model registry, a **FastAPI** inference API, monitoring with **Elasticsearch/Kibana**, and a fully automated **GitHub Actions** CI/CD workflow.

---

## Repository Structure

```
.
├── .github/workflows/
│   └── mlops_pipeline.yml       # CI/CD pipeline
├── data/
│   ├── raw/                     # Raw CSVs (gitignore'd)
│   └── processed/               # Preprocessed CSVs
├── models/                      # Serialised model artefacts
├── mlruns/                      # MLflow experiment tracking
├── notebooks/                   # Jupyter exploration notebooks
├── src/
│   ├── data/
│   │   ├── preprocess_6g.py     # 6G preprocessing & sequence builder
│   │   └── validate.py          # Data-quality validation
│   ├── models/
│   │   └── train_congestion_6g.py  # LSTM training script (MLflow)
│   ├── api/
│   │   ├── main.py              # FastAPI application
│   │   ├── schemas.py           # Pydantic I/O schemas
│   │   └── predict.py           # Inference helpers
│   └── monitoring/
│       └── log_sender.py        # Elasticsearch prediction logger
├── tests/
│   ├── test_preprocessing.py    # Unit tests – preprocessing
│   ├── test_models.py           # Unit tests – model forward pass
│   ├── test_api.py              # Functional tests – FastAPI
│   ├── test_model_quality.py    # Quality-gate tests – MLflow metrics
│   └── test_data_validation.py  # Data tests – processed CSV
├── Dockerfile
├── docker-compose.yml
├── MLproject
├── Makefile
└── requirements.txt
```

---

## Quick Start

```bash
# 1. Install dependencies
make setup

# 2. Preprocess data and validate
make data
make validate-data

# 3. Train the congestion LSTM
make train-congestion

# 4. Run all tests (including quality gate)
make test

# 5. Open MLflow UI
make mlflow-ui          # http://localhost:5000

# 6. Serve the API
make serve              # http://localhost:8000/docs

# 7. Start the full stack (Docker Compose)
make docker-compose-up
```

Or run the entire pipeline in one command:

```bash
make pipeline
```

---

## Makefile Targets

| Target | Description |
|---|---|
| `setup` | Install all pinned Python dependencies |
| `lint` | Flake8 (max line length 120) |
| `format` | Black auto-format |
| `security` | Bandit high-severity scan |
| `quality` | lint + security |
| `data` | Run `src/data/preprocess_6g.py` |
| `validate-data` | Run `src/data/validate.py` |
| `train-slice-5g` | Train slice-selection model (5G) |
| `train-slice-6g` | Train slice-selection model (6G) |
| `train-sla` | Train SLA-adherence model |
| `train-congestion` | Train LSTM congestion model |
| `train-anomaly` | Train anomaly-detection model |
| `train-all` | Train all five models |
| `test` | Run `pytest tests/` |
| `mlflow-ui` | Start MLflow tracking server on port 5000 |
| `serve` | Start FastAPI on port 8000 (hot-reload) |
| `docker-build` | Build the API Docker image |
| `docker-run` | Run the API container |
| `docker-compose-up` | Start api + mlflow + elasticsearch + kibana |
| `notebook` | Open Jupyter with the notebooks/ directory |
| `pipeline` | Full pipeline: setup → lint → security → validate-data → train-congestion → test |
| `clean` | Remove `.pyc`, `__pycache__`, `.pytest_cache` |

---

## MLflow Tracking

After training, open the UI:

```
http://localhost:5000
```

| Experiment | Registry Name | Primary Metric | Gate |
|---|---|---|---|
| `congestion-forecast-6g` | `congestion-lstm-6g` | `val_mae` | < 5.0 |

---

## FastAPI Swagger UI

```
http://localhost:8000/docs
```

Endpoints:

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/predict/congestion` | LSTM congestion forecast |
| POST | `/predict/slice` | Slice-selection recommendation |
| POST | `/predict/anomaly` | Anomaly detection |

---

## Docker Compose

```bash
docker-compose up -d
```

| Service | Port | Image |
|---|---|---|
| api | 8000 | local build |
| mlflow | 5000 | ghcr.io/mlflow/mlflow:v2.13.0 |
| elasticsearch | 9200 | elasticsearch:8.13.4 (single-node, no security) |
| kibana | 5601 | kibana:8.13.4 |

---

## Implementation Checklist

- [x] Repository directory structure
- [x] `requirements.txt` with pinned dependencies
- [x] `Makefile` with all targets
- [x] `src/data/preprocess_6g.py`
- [x] `src/data/validate.py`
- [x] `src/models/train_congestion_6g.py`
- [x] `MLproject`
- [x] `src/api/schemas.py`
- [x] `src/api/predict.py`
- [x] `src/api/main.py`
- [x] `src/monitoring/log_sender.py`
- [x] `tests/test_preprocessing.py`
- [x] `tests/test_models.py`
- [x] `tests/test_api.py`
- [x] `tests/test_model_quality.py`
- [x] `tests/test_data_validation.py`
- [x] `Dockerfile`
- [x] `docker-compose.yml`
- [x] `.github/workflows/mlops_pipeline.yml`
- [x] `README.md`

---

## Contributors

| Name | Role |
|---|---|
| Ahmed Bouhlel | ML Engineering |
| Rayen Sebai | MLOps / DevOps |
| Mouhamed Dhia Chaouachi | Data Engineering |
| Fourat Hamdi | API Development |
| Mouhamed Aziz Weslati | Monitoring |
| Mouhamed Aziz Boughanmi | Data Science |

**Academic context:** Esprit School of Engineering · Projet Intégré 4ème année DATA · Azerty67 · 2025/2026  
**Mentors:** Rahma Bouraoui · Safa Cherif · Ameni Mejri