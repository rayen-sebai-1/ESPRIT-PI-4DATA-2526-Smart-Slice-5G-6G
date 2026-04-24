# Batch Orchestrator

This project now supports two offline-learning modes:

- local fallback mode: `MLFLOW_TRACKING_URI` unset, training logs to `sqlite:///mlflow.db`
- Scenario B mode: `docker compose` runs MLflow with PostgreSQL metadata and MinIO artifacts

The authoritative integrated Docker runtime now lives in `neuroslice-platform/infrastructure/docker-compose.yml`. The local `batch-orchestrator/docker-compose.yml` remains available as an isolated MLOps-only stack.

Do not run the isolated MLOps stack and the integrated infrastructure stack at the same time unless you override host ports, because both publish MLflow, MinIO, Elasticsearch, Logstash, and Kibana on the same defaults.

## Scenario B Flow

Each training script keeps its existing model fit and MLflow logging, then adds:

1. evaluation and quality-gate checks
2. local artifact persistence under `models/`
3. ONNX export under `models/onnx/`
4. FP16 conversion and ONNX validation
5. MLflow artifact logging for original and ONNX artifacts
6. registry metadata append in `models/registry.json`

Generated registry fields include:

- `model_name`
- `model_family`
- `version`
- `created_at`
- `run_id`
- `metrics`
- `quality_gate_status`
- `artifact_format`
- `local_artifact_path`
- `mlflow_artifact_uri`
- `onnx_fp16_path`
- `onnx_export_status`
- `promotion_status`
- `reason`

## Promotion Rules

- `sla_5g`: promote when `val_roc_auc >= 0.75`
- `sla_6g`: promote when `val_roc_auc >= 0.75`
- `slice_type_5g`: promote when `val_accuracy >= 0.80`
- `slice_type_6g`: promote when `val_accuracy >= 0.80`; warn when `val_accuracy == 1.0`
- `congestion_6g`: promote when `val_mae < 5.0`
- `congestion_5g`: promote only when `val_precision >= 0.50` and `val_recall >= 0.70`

## Docker Services

`docker-compose.yml` now provisions:

- `postgres` for the MLflow backend store
- `minio` for the artifact bucket
- `minio-init` to create the artifact bucket
- `mlflow` configured with PostgreSQL and MinIO
- `logstash` for HTTP log ingestion into Elasticsearch
- `api` exposed on `8010` by default

Copy `.env.example` to `.env` when you want the Docker-backed configuration.

## Commands

```bash
cd neuroslice-platform/mlops-tier/batch-orchestrator
pip install -r requirements.txt
make pipeline
make model-report
```

Integrated runtime:

```bash
cd neuroslice-platform/infrastructure
docker compose up --build mlflow-postgres minio minio-init mlflow mlops-api elasticsearch logstash kibana
```

## Generated Outputs

- `models/registry.json`
- `models/onnx/*.onnx`
- `reports/model_training_summary.md`

If ONNX export fails for a specific model, the training pipeline keeps running, the original artifact remains available, and the failure reason is written into the registry metadata.

## Logstash

The local observability stack now includes Logstash between application log emission and Elasticsearch:

- `src/monitoring/log_sender.py` sends to `LOGSTASH_HTTP_URL` when `LOG_MONITORING_MODE=logstash`
- if Logstash is unavailable, the sender falls back to direct Elasticsearch indexing
- the Logstash pipeline lives in `logstash/pipeline/logstash.conf`

Default local endpoint:

```bash
http://localhost:8081/predictions
```
