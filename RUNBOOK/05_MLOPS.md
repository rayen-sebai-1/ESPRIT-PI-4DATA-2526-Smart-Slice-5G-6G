# 05 MLOps

## Lifecycle (source-defined)
```text
preprocess -> train -> MLflow log/register
-> export ONNX -> convert FP16 -> validate
-> update registry.json -> promote current pointer
-> runtime AIOps hot reload
```

## Required model families in Scenario B
- `congestion_5g`
- `sla_5g`
- `slice_type_5g`

Preprocessing scripts and training scripts exist under:
- `mlops-tier/batch-orchestrator/src/data/`
- `mlops-tier/batch-orchestrator/src/models/`

## Promotion artifact structure
Runtime contract path:

```text
models/promoted/{model_name}/current/
  model_fp16.onnx
  metadata.json
  version.txt
  drift_reference.npz
  drift_feature_schema.json
```

## Runtime AIOps model loading
Compose mounts read-only for workers:
- `../mlops-tier/batch-orchestrator/models:/mlops/models:ro`
- `../mlops-tier/batch-orchestrator/data:/mlops/data:ro`

Workers poll metadata (`MODEL_POLL_INTERVAL_SEC`) and reload when promoted artifacts change.

## `mlops-runner` behavior
`mlops-runner` is internal-only and executes only fixed action keys via `/run-action`.

Security properties:
- allowlisted action map (`_ACTION_MAP`)
- optional bearer token (`MLOPS_RUNNER_TOKEN`)
- no arbitrary shell command from API payload
- logs truncated to bounded size

## Dashboard orchestration path
```text
React /mlops/operations
  -> /api/dashboard/mlops/pipeline/run (Kong)
  -> dashboard-backend
  -> mlops-runner /run-action { action: full_pipeline, trigger_source: manual }
```

Run history is persisted in:
- `dashboard.mlops_pipeline_runs`

## Runtime evaluation surface

Scenario B monitoring includes online evaluation metrics produced by `aiops-tier/online-evaluator` and exposed through:

- `GET /api/v1/evaluation/latest`
- `GET /api/v1/evaluation/latest/{model_name}`
- `GET /api/dashboard/mlops/evaluation`
- `GET /api/dashboard/mlops/evaluation/{model_name}`
