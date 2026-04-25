# =============================================================================
# Smart Slice 5G/6G MLOps Makefile
# =============================================================================

PYTHON := python
PIP := pip
-include .env

MLFLOW_PORT ?= 5000
API_PORT ?= 8010
DATA_SRC_DIR := src/data
MODEL_SRC_DIR := src/models
MLFLOW_TRACKING_URI ?= sqlite:///mlflow.db
MLFLOW_BACKEND_STORE_URI ?= $(MLFLOW_TRACKING_URI)
MLFLOW_ARTIFACT_ROOT ?= ./mlruns
AWS_ACCESS_KEY_ID ?=
AWS_SECRET_ACCESS_KEY ?=
MLFLOW_S3_ENDPOINT_URL ?=
MINIO_ROOT_USER ?= minioadmin
MINIO_ROOT_PASSWORD ?= minioadmin123
POSTGRES_USER ?= mlflow
POSTGRES_PASSWORD ?= mlflow123
POSTGRES_DB ?= mlflow

export MLFLOW_TRACKING_URI MLFLOW_BACKEND_STORE_URI MLFLOW_ARTIFACT_ROOT
export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY MLFLOW_S3_ENDPOINT_URL
export MINIO_ROOT_USER MINIO_ROOT_PASSWORD POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB
export API_PORT MLFLOW_PORT

.PHONY: setup lint format security quality data data-sla-5g data-sla-6g data-congestion-5g data-slice-type-5g \
        validate-data validate-data-sla-5g validate-data-sla-6g validate-data-congestion-5g validate-data-slice-type-5g \
        train-sla-5g train-sla-6g train-congestion-5g train-congestion-6g \
        train-slice-type-5g train-slice-type-6g \
        train-all test model-report mlflow-ui serve docker-build docker-run \
        docker-compose-up notebook pipeline clean

# ------------------------------------------------------------------------------
# Environment Setup
# ------------------------------------------------------------------------------
setup:
	$(PIP) install -r requirements.txt

# ------------------------------------------------------------------------------
# Code Quality
# ------------------------------------------------------------------------------
lint:
	flake8 src/ tests/ --max-line-length=120

format:
	black src/ tests/ --line-length=120

security:
	bandit -r src/ -ll

quality: lint security

# ------------------------------------------------------------------------------
# Data
# ------------------------------------------------------------------------------
data:
	$(PYTHON) $(DATA_SRC_DIR)/preprocess_6g.py

data-sla-5g:
	$(PYTHON) $(DATA_SRC_DIR)/preprocess_sla_5g.py

data-sla-6g:
	$(PYTHON) $(DATA_SRC_DIR)/preprocess_sla_6g.py

data-congestion-5g:
	$(PYTHON) $(DATA_SRC_DIR)/preprocess_congestion_5g.py

validate-data: data
	$(PYTHON) $(DATA_SRC_DIR)/validate.py

validate-data-sla-5g:
	$(PYTHON) $(DATA_SRC_DIR)/validate_sla_5g.py

validate-data-sla-6g:
	$(PYTHON) $(DATA_SRC_DIR)/validate_sla_6g.py

validate-data-congestion-5g:
	$(PYTHON) $(DATA_SRC_DIR)/validate_congestion_5g.py

data-slice-type-5g:
	$(PYTHON) $(DATA_SRC_DIR)/preprocess_slice_type_5g.py

validate-data-slice-type-5g:
	$(PYTHON) $(DATA_SRC_DIR)/validate_slice_type_5g.py

data-slice-type-6g:
	$(PYTHON) $(DATA_SRC_DIR)/preprocess_slice_type_6g.py

validate-data-slice-type-6g:
	$(PYTHON) $(DATA_SRC_DIR)/validate_slice_type_6g.py

# ------------------------------------------------------------------------------
# Training
# ------------------------------------------------------------------------------
train-sla-5g:
	$(PYTHON) -m src.models.train_sla_5g

train-sla-6g:
	$(PYTHON) -m src.models.train_sla_6g

train-congestion-5g:
	$(PYTHON) -m src.models.train_congestion_5g

train-congestion-6g:
	$(PYTHON) -m src.models.train_congestion_6g

train-slice-type-5g:
	$(PYTHON) -m src.models.train_slice_type_5g

train-slice-type-6g:
	$(PYTHON) -m src.models.train_slice_type_6g

train-all: train-sla-5g train-sla-6g train-congestion-5g train-congestion-6g train-slice-type-5g train-slice-type-6g

# ------------------------------------------------------------------------------
# Testing
# ------------------------------------------------------------------------------
test:
	pytest tests/ -v

model-report:
	$(PYTHON) -m src.reports.generate_model_report

# ------------------------------------------------------------------------------
# MLflow
# ------------------------------------------------------------------------------
mlflow-ui:
	mlflow ui --port $(MLFLOW_PORT) --backend-store-uri $(MLFLOW_BACKEND_STORE_URI)

# ------------------------------------------------------------------------------
# API
# ------------------------------------------------------------------------------
serve:
	uvicorn src.api.main:app --host 0.0.0.0 --port $(API_PORT) --reload

# ------------------------------------------------------------------------------
# Docker
# ------------------------------------------------------------------------------
docker-build:
	docker build -t smart-slice-api .

docker-run:
	docker run -e API_PORT=$(API_PORT) -p $(API_PORT):$(API_PORT) smart-slice-api

docker-compose-up:
	docker-compose up -d


# ------------------------------------------------------------------------------
# Full Pipeline
# ------------------------------------------------------------------------------
pipeline: setup lint security validate-data data-sla-5g data-sla-6g data-congestion-5g data-slice-type-5g data-slice-type-6g \
          validate-data-sla-5g validate-data-sla-6g validate-data-congestion-5g validate-data-slice-type-5g validate-data-slice-type-6g \
          train-congestion-6g train-congestion-5g train-sla-5g train-sla-6g train-slice-type-5g train-slice-type-6g model-report test

# ------------------------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------------------------
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	rm -rf dist/ build/ *.egg-info/
