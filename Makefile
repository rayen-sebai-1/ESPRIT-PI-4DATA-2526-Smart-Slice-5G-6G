# =============================================================================
# Smart Slice 5G/6G MLOps Makefile
# =============================================================================

PYTHON := python
PIP := pip
MLFLOW_PORT := 5000
API_PORT := 8000

.PHONY: setup lint format security quality data validate-data \
        train-slice-5g train-slice-6g train-sla train-congestion train-anomaly \
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
	$(PYTHON) src/data/preprocess_6g.py

validate-data:
	$(PYTHON) src/data/validate.py

# ------------------------------------------------------------------------------
# Training
# ------------------------------------------------------------------------------
train-slice-5g:
	$(PYTHON) src/models/train_slice_5g.py

train-slice-6g:
	$(PYTHON) src/models/train_slice_6g.py

train-sla:
	$(PYTHON) src/models/train_sla.py

train-congestion:
	$(PYTHON) src/models/train_congestion_6g.py

train-anomaly:
	$(PYTHON) src/models/train_anomaly.py

train-all: train-slice-5g train-slice-6g train-sla train-congestion train-anomaly

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
pipeline: setup lint security validate-data train-congestion test

# ------------------------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------------------------
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	rm -rf dist/ build/ *.egg-info/
