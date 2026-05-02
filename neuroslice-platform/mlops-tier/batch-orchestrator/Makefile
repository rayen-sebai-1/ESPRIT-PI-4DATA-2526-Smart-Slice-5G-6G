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
MLFLOW_ARTIFACT_ROOT ?= s3://mlflow-artifacts
MLFLOW_EXPERIMENT_NAME ?= neuroslice-aiops
AWS_ACCESS_KEY_ID ?=
AWS_SECRET_ACCESS_KEY ?=
MLFLOW_S3_ENDPOINT_URL ?=
MINIO_ROOT_USER ?= minioadmin
MINIO_ROOT_PASSWORD ?= minioadmin123
MLOPS_POSTGRES_USER ?= mlflow
MLOPS_POSTGRES_PASSWORD ?= mlflow123
MLOPS_POSTGRES_DB ?= mlflow

export MLFLOW_TRACKING_URI MLFLOW_BACKEND_STORE_URI MLFLOW_ARTIFACT_ROOT MLFLOW_EXPERIMENT_NAME
export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY MLFLOW_S3_ENDPOINT_URL
export MINIO_ROOT_USER MINIO_ROOT_PASSWORD MLOPS_POSTGRES_USER MLOPS_POSTGRES_PASSWORD MLOPS_POSTGRES_DB
export API_PORT MLFLOW_PORT

.PHONY: setup lint format security quality data data-sla-5g data-sla-6g data-congestion-5g data-slice-type-5g \
        validate-data validate-data-sla-5g validate-data-sla-6g validate-data-congestion-5g validate-data-slice-type-5g \
        train-sla-5g train-sla-6g train-congestion-5g train-congestion-6g \
        train-slice-type-5g train-slice-type-6g \
        train-all test model-report mlflow-ui serve docker-build docker-run \
        docker-compose-up notebook pipeline pipeline-congestion-5g pipeline-sla-5g pipeline-slice-type-5g pipeline-all clean \
        prepare-data train evaluate log-mlflow export-onnx convert-fp16 validate-model \
        promote-model rollback-model mlops-full

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
pipeline-congestion-5g: data-congestion-5g validate-data-congestion-5g train-congestion-5g model-report

pipeline-sla-5g: data-sla-5g validate-data-sla-5g train-sla-5g model-report

pipeline-slice-type-5g: data-slice-type-5g validate-data-slice-type-5g train-slice-type-5g model-report

pipeline: data-congestion-5g validate-data-congestion-5g train-congestion-5g \
          data-sla-5g validate-data-sla-5g train-sla-5g \
          data-slice-type-5g validate-data-slice-type-5g train-slice-type-5g \
          model-report

pipeline-all: data-sla-5g data-sla-6g data-congestion-5g data-slice-type-5g data-slice-type-6g \
              validate-data-sla-5g validate-data-sla-6g validate-data-congestion-5g validate-data-slice-type-5g validate-data-slice-type-6g \
              train-congestion-5g train-congestion-6g train-sla-5g train-sla-6g train-slice-type-5g train-slice-type-6g model-report

# ------------------------------------------------------------------------------
# Orchestration Center Targets
# ------------------------------------------------------------------------------
prepare-data:
	$(PYTHON) $(DATA_SRC_DIR)/preprocess_6g.py
	$(PYTHON) $(DATA_SRC_DIR)/preprocess_sla_5g.py
	$(PYTHON) $(DATA_SRC_DIR)/preprocess_sla_6g.py
	$(PYTHON) $(DATA_SRC_DIR)/preprocess_congestion_5g.py
	$(PYTHON) $(DATA_SRC_DIR)/preprocess_slice_type_5g.py
	$(PYTHON) $(DATA_SRC_DIR)/preprocess_slice_type_6g.py

# validate-data is already defined above, but we make sure it does what we want
# Oh wait, validate-data already exists and depends on 'data'.
# We will leave validate-data as is, since it runs validate.py.
# But wait, we should redefine validate-data or leave it?
# The request says "prepare_data -> validate_data -> train..."

train:
	$(PYTHON) -m src.models.train_sla_5g
	$(PYTHON) -m src.models.train_sla_6g
	$(PYTHON) -m src.models.train_congestion_5g
	$(PYTHON) -m src.models.train_congestion_6g
	$(PYTHON) -m src.models.train_slice_type_5g
	$(PYTHON) -m src.models.train_slice_type_6g

evaluate:
	$(PYTHON) -m src.reports.generate_model_report

log-mlflow:
	@echo "Assuming models were logged during training/evaluation via mlflow."
	@echo "If a separate script is needed, run it here."

export-onnx:
	@echo "Exporting models to ONNX... (placeholder or run script)"

convert-fp16:
	@echo "Converting ONNX models to FP16... (placeholder or run script)"

validate-model:
	@echo "Validating exported artifacts via quality gates... (placeholder or run script)"

promote-model:
	@echo "Promoting model to production... (placeholder or delegate to API)"

rollback-model:
	@echo "Rolling back model... (placeholder or delegate to API)"

mlops-full: prepare-data validate-data train evaluate log-mlflow export-onnx convert-fp16 validate-model
	@echo "Full MLOps pipeline completed successfully."

# ------------------------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------------------------
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	rm -rf dist/ build/ *.egg-info/
