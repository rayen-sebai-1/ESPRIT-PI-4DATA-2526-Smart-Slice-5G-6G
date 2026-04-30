# AIOps Tier

Last verified: 2026-04-29.

The AIOps tier contains online inference workers that consume normalized telemetry and emit runtime prediction events and latest-state summaries.

## Implemented Services

- `congestion-detector/`: congestion anomaly scoring
- `slice-classifier/`: slice type classification and mismatch detection
- `sla-assurance/`: SLA risk scoring
- `drift-monitor/`: **Scenario B drift detection** — Alibi Detect MMD
- `shared/`: Redis, model registry, ONNX Runtime, and hot-reload helpers

The three inference workers are background workers with no public HTTP APIs. The `drift-monitor` exposes `GET /health`, `GET /drift/latest`, `GET /drift/latest/{model_name}`, and `GET /metrics` (Prometheus).

## Runtime Streams

Shared input:

- Redis stream `stream:norm.telemetry`

Outputs:

- `congestion-detector` -> `events.anomaly`, Redis state prefix `aiops:congestion`, Influx measurement `aiops_congestion`
- `slice-classifier` -> `events.slice.classification`, Redis state prefix `aiops:slice_classification`, Influx measurement `aiops_slice_classification`
- `sla-assurance` -> `events.sla`, Redis state prefix `aiops:sla`, Influx measurement `aiops_sla`
- `drift-monitor` -> `events.drift`, Redis state prefix `aiops:drift`, Kafka topic `drift.alert`, Influx measurement `aiops_drift`

Kafka and InfluxDB mirroring are enabled by default in `infrastructure/docker-compose.yml`.

## Scenario B Drift Detection

The `drift-monitor` is an adaptation of the architecture report's Alibi Detect sidecar design for Docker Compose. One service monitors all three models; it can be split into per-model sidecars without schema changes.

- **Method**: Alibi Detect MMD (`alibi_detect.cd.MMDDrift`, PyTorch backend)
- **Window size**: 500 samples per model (rolling)
- **p-value threshold**: p < 0.01
- **Test interval**: every 60 s
- **Emit cooldown**: 300 s (suppresses repeated alerts)
- **Auto-trigger MLOps**: OFF by default (`DRIFT_AUTO_TRIGGER_MLOPS=false`)

The `drift-monitor` is behind the `drift` Docker Compose profile because alibi-detect includes PyTorch:

```bash
docker compose --profile drift up --build
```

See `SCENARIO_B_DRIFT_DETECTION.md` for the full design, drift event contract, and verification commands.

## Production Model Loading

The production model source is the promoted-current ONNX FP16 artifact created by the MLOps lifecycle:

```text
/mlops/models/promoted/{MODEL_NAME}/current/model_fp16.onnx
/mlops/models/promoted/{MODEL_NAME}/current/metadata.json
```

Configured model names:

- `congestion-detector`: `MODEL_NAME=congestion_5g`
- `slice-classifier`: `MODEL_NAME=slice_type_5g`
- `sla-assurance`: `MODEL_NAME=sla_5g`

Model format:

- `MODEL_FORMAT=onnx_fp16`

All services use ONNX Runtime for promoted-current models. `congestion-detector` no longer loads the legacy TorchScript `.pt` model in normal runtime. If promoted ONNX is unavailable, it stays in heuristic fallback mode instead of silently loading `.pt`.

## Hot Reload

Each service starts a background reload task:

1. read `current/metadata.json`
2. compare metadata version and file timestamps with the loaded bundle
3. load a new ONNX Runtime session from `current/model_fp16.onnx` when the version or model file changes
4. replace the in-memory model bundle without restarting the container

Reload interval:

- `MODEL_POLL_INTERVAL_SEC`, default `60`

Successful reload logs include:

```text
Hot-reloaded congestion model to version=...
Hot-reloaded SLA model to version=...
Hot-reloaded slice model to version=...
```

## Runtime Mounts

The integrated Compose stack mounts MLOps outputs read-only:

- `../mlops-tier/batch-orchestrator/models:/mlops/models:ro`
- `../mlops-tier/batch-orchestrator/data:/mlops/data:ro`
- `../mlops-tier/batch-orchestrator/src:/mlops/src:ro`

Required promoted model paths:

- `/mlops/models/promoted/congestion_5g/current/model_fp16.onnx`
- `/mlops/models/promoted/sla_5g/current/model_fp16.onnx`
- `/mlops/models/promoted/slice_type_5g/current/model_fp16.onnx`

Preprocessing artifacts, when present:

- `CONGESTION_PREPROCESSOR_PATH=/mlops/data/processed/preprocessor_congestion_5g.pkl`
- `SLA_SCALER_PATH=/mlops/data/processed/scaler_sla_5g.pkl`
- `SLICE_LABEL_ENCODER_PATH=/mlops/data/processed/label_encoder_slice_type_5g.pkl`

## Fallback Behavior

- If promoted ONNX cannot be loaded, workers continue serving heuristic outputs.
- `fallbackMode=false` when a promoted ONNX FP16 model is loaded successfully.
- `fallbackMode=true` only when no usable runtime model is loaded or inference falls back to heuristic behavior.

## Verification

```bash
cd neuroslice-platform/aiops-tier
PYTHONDONTWRITEBYTECODE=1 pytest tests/test_model_registry_client.py -q
```

Runtime checks:

```bash
docker compose logs -f congestion-detector
docker compose logs -f sla-assurance
docker compose logs -f slice-classifier
```

Look for `model_format=onnx_fp16`, `fallback_mode=False`, and hot-reload log lines after a new promotion.

## Current Limits

- `misrouting-detector` is deferred.
- Services do not download remote MLflow artifacts directly at runtime; they read the local promoted artifacts mounted from the batch orchestrator.
- Generated promoted models must exist locally for model-backed inference. Otherwise the heuristic path remains active.
