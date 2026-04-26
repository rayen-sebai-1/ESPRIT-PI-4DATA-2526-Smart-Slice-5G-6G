# Batch Orchestrator

`batch-orchestrator` is the active NeuroSlice MLOps project. It contains preprocessing, validation, model training, MLflow lifecycle integration, ONNX export, FP16 conversion, model promotion, the prediction API, tests, notebooks, and generated reports.

## Scope

Current responsibilities:

- data preprocessing and validation for 5G/6G datasets
- training for congestion, SLA, and slice-type models
- MLflow tracking and model registration
- ONNX export for PyTorch, XGBoost, and LightGBM models
- ONNX FP16 conversion with `onnxconverter-common`
- production model promotion into `models/promoted/`
- local registry metadata in `models/registry.json`
- FastAPI prediction service
- model report generation
- automated tests for data, export, lifecycle, quality gates, and API behavior

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

Manual offline worker against integrated services:

```bash
cd neuroslice-platform/infrastructure
docker compose --profile mlops --profile mlops-worker run --rm mlops-worker
```

The default integrated worker runs the 5G production lifecycle for:

1. `congestion_5g`
2. `sla_5g`
3. `slice_type_5g`
4. model report generation

## Common Commands

```bash
make data
make validate-data
make train-all
make pipeline-congestion-5g
make pipeline
make pipeline-all
make model-report
make test
make serve
```

Task-specific commands:

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
- `src/models/`: training scripts and lifecycle registry code
- `src/mlops/`: ONNX export and promotion helpers
- `src/api/`: prediction API
- `src/reports/`: model report generation
- `tests/`: API, preprocessing, lifecycle, export, registry, and quality tests
- `notebooks/`: exploratory modeling notebooks
- `data/raw/`: committed source datasets
- `data/processed/`: generated preprocessing outputs
- `models/`: generated model, ONNX, registry, and promotion artifacts
- `reports/`: generated Markdown summaries
- `report/`: project PDF report asset

## MLflow and Artifact Storage

Integrated defaults:

- MLflow experiment: `neuroslice-aiops`
- tracking URI: `http://mlflow-server:5000`
- backend store: `mlops-postgres`
- artifact root: `s3://mlflow-artifacts`
- MinIO endpoint: `http://minio:9000`
- MinIO bucket: `mlflow-artifacts`

Training scripts log model binaries, preprocessors/scalers/encoders, ONNX artifacts, FP16 artifacts, metrics, and status reports. ONNX export failures are recorded in MLflow and registry metadata without necessarily failing the whole training run.

## Promotion Contract

After ONNX export, the lifecycle code promotes production candidates into:

```text
models/promoted/{model_name}/{version}/model.onnx
models/promoted/{model_name}/{version}/model_fp16.onnx
models/promoted/{model_name}/{version}/metadata.json
models/promoted/{model_name}/current/model.onnx
models/promoted/{model_name}/current/model_fp16.onnx
models/promoted/{model_name}/current/metadata.json
models/promoted/{model_name}/current/version.txt
```

`src/mlops/promotion.py` provides:

- `convert_to_fp16(model_path, output_path)`
- `convert_onnx_to_fp16(source_path, target_path, keep_fp32_io=True)`
- `promote_onnx_artifacts(...)`
- `validate_promoted_artifacts(...)`
- `materialize_promoted_model_for_registry(...)`

The promotion update validates that raw ONNX and FP16 ONNX exist, pass ONNX checker, and that FP16 loads with ONNX Runtime before `current/` metadata is updated.

## Registry Metadata

Every training run appends an entry to `models/registry.json`. Production selection uses the configured quality gate and task metric. Promotion fields include:

- `model_name`
- `registered_model_name`
- `mlflow_model_version`
- `deployment_version`
- `stage`
- `promoted`
- `onnx_export_status`
- `promoted_current_fp16_path`
- `promoted_current_metadata_path`

The runtime services use promoted-current artifacts rather than raw MLflow artifacts.

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

Default URL with the integrated `mlops` profile:

- `http://localhost:8010`

## Generated Outputs

The following are generated runtime artifacts and may change after training:

- `models/registry.json`
- `models/promoted/`
- `models/onnx/`
- `models/*.pt`, `models/*.pth`, `models/*.pkl`, `models/*.ubj`, `models/*.onnx`
- `data/processed/`
- `reports/model_training_summary.md`
- `mlruns/`, `mlflow.db`

Do not treat these as hand-written source files.

## Verification

```bash
cd neuroslice-platform/mlops-tier/batch-orchestrator
pytest tests -v
```

Focused deployment checks:

```bash
pytest tests/test_model_lifecycle_registry.py tests/test_export_onnx.py -q
```

Runtime read-only ONNX check after promotion:

```bash
python -c "import pathlib, json, onnxruntime as ort; p=pathlib.Path('models/promoted/sla_5g/current/model_fp16.onnx'); ort.InferenceSession(str(p)); print(json.loads((p.parent/'metadata.json').read_text())['version'])"
```
