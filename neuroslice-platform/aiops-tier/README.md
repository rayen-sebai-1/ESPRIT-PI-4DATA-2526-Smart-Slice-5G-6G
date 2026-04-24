# AIOps Tier

The AIOps tier contains the online inference workers:

- `congestion-detector/`
- `sla-assurance/`
- `slice-classifier/`

## Model Loading

The services now include a Scenario B integration scaffold:

1. read `MODEL_REGISTRY_PATH` through `shared/model_registry_client.py`
2. look for the latest `promotion_status=promoted` entry for `MODEL_NAME`
3. if `MODEL_FORMAT=onnx_fp16` exists, load it with ONNX Runtime
4. otherwise fall back to the previous loader path
5. if no model can be loaded, keep the existing heuristic behavior

Current runtime logging now reports:

- `model_loaded`
- `model_format`
- `model_version`
- `fallback_mode`
- `onnxruntime_enabled`

## Shared Registry Env Vars

All current services support these generic model-discovery variables:

- `MODEL_REGISTRY_PATH`
- `MODEL_POLL_INTERVAL_SEC`
- `MODEL_NAME`
- `MODEL_FORMAT`

Existing service-specific variables remain valid and are still used for fallback:

- `CONGESTION_MODEL_PATH`
- `CONGESTION_PREPROCESSOR_PATH`
- `SLA_MODEL_PATH`
- `SLA_MODEL_NAME`
- `SLICE_MODEL_PATH`
- `SLICE_MODEL_NAME`
- `MLFLOW_DB_PATH`
- `MLRUNS_DIR`

## Current Defaults

- `congestion-detector`: `MODEL_NAME=congestion_5g`
- `sla-assurance`: `MODEL_NAME=sla_5g`
- `slice-classifier`: `MODEL_NAME=slice_type_5g`
- `MODEL_FORMAT=onnx_fp16`

## Hot Reload Scaffold

`shared/model_registry_client.py` exposes `should_reload_model(current_version, model_name)`. The current change only adds the discovery and comparison scaffold. Direct MLflow or MinIO download and background polling remain TODOs.

## Runtime Dependency

These services still expect the MLOps project to be mounted at `/mlops`. Promoted ONNX FP16 artifacts are resolved from `models/registry.json`, usually under `/mlops/models/onnx/`.
