# =============================================================================
# Smart Slice 5G/6G MLOps Makefile
# =============================================================================

PYTHON := python
PIP := pip
MLFLOW_PORT := 5000
API_PORT := 8000
DATA_SRC_DIR := src/data
MODEL_SRC_DIR := src/models

.PHONY: setup lint format security quality data data-sla-5g data-sla-6g data-congestion-5g data-slice-type-5g \
        validate-data validate-data-sla-5g validate-data-sla-6g validate-data-congestion-5g validate-data-slice-type-5g \
        train-sla-5g train-sla-6g train-congestion-5g train-congestion-6g \
        train-slice-type-5g train-slice-type-6g \
        train-all test mlflow-ui serve docker-build docker-run \
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

validate-data:
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
	$(PYTHON) $(MODEL_SRC_DIR)/train_sla_5g.py

train-sla-6g:
	$(PYTHON) $(MODEL_SRC_DIR)/train_sla_6g.py

train-congestion-5g:
	$(PYTHON) $(MODEL_SRC_DIR)/train_congestion_5g.py

train-congestion-6g:
	$(PYTHON) $(MODEL_SRC_DIR)/train_congestion_6g.py

train-slice-type-5g:
	$(PYTHON) $(MODEL_SRC_DIR)/train_slice_type_5g.py

train-slice-type-6g:
	$(PYTHON) $(MODEL_SRC_DIR)/train_slice_type_6g.py

train-all: train-sla-5g train-sla-6g train-congestion-5g train-congestion-6g train-slice-type-5g train-slice-type-6g

# ------------------------------------------------------------------------------
# Testing
# ------------------------------------------------------------------------------
test:
	pytest tests/ -v

# ------------------------------------------------------------------------------
# MLflow
# ------------------------------------------------------------------------------
mlflow-ui:
	mlflow ui --port $(MLFLOW_PORT)

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
	docker run -p $(API_PORT):$(API_PORT) smart-slice-api

docker-compose-up:
	docker-compose up -d


# ------------------------------------------------------------------------------
# Full Pipeline
# ------------------------------------------------------------------------------
pipeline: setup lint security validate-data data-sla-5g data-sla-6g data-congestion-5g data-slice-type-5g data-slice-type-6g \
          validate-data-sla-5g validate-data-sla-6g validate-data-congestion-5g validate-data-slice-type-5g validate-data-slice-type-6g \
          train-congestion-6g train-congestion-5g train-sla-5g train-sla-6g train-slice-type-5g train-slice-type-6g test

# ------------------------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------------------------
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	rm -rf dist/ build/ *.egg-info/
