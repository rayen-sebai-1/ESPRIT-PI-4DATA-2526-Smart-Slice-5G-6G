# Scenario B — Drift Detection Implementation

## 1. Summary

This document describes the Alibi Detect MMD drift detection feature added to Scenario B (Docker Compose local prototype).

The design adapts the architecture report's "Alibi Detect sidecars" concept to Docker Compose: instead of per-model sidecars, a single `drift-monitor` service monitors all three AIOps model inputs. The service can be split into per-model sidecars later without any schema changes.

**Misrouting detection remains excluded.** This implementation covers input-feature drift only.

**Auto-trigger of MLOps retraining is OFF by default.** Drift produces an alert and recommendation; an operator must manually trigger the MLOps pipeline from the dashboard.

---

## 2. Files Changed

### New files

| File | Purpose |
|------|---------|
| `aiops-tier/drift-monitor/Dockerfile` | Container image for drift-monitor |
| `aiops-tier/drift-monitor/requirements.txt` | Python deps incl. `alibi-detect[torch]` |
| `aiops-tier/drift-monitor/app/main.py` | FastAPI app + background tasks |
| `aiops-tier/drift-monitor/app/config.py` | Env-driven configuration |
| `aiops-tier/drift-monitor/app/consumer.py` | Redis stream consumer + drift test loop |
| `aiops-tier/drift-monitor/app/feature_extractor.py` | Per-model feature extraction |
| `aiops-tier/drift-monitor/app/alibi_detector.py` | Alibi Detect MMD wrapper |
| `aiops-tier/drift-monitor/app/drift_store.py` | Redis state + stream writes |
| `aiops-tier/drift-monitor/app/redis_client.py` | Redis connection helper |
| `aiops-tier/drift-monitor/app/kafka_client.py` | Kafka producer helper |
| `aiops-tier/drift-monitor/app/influx_client.py` | InfluxDB write helper |
| `aiops-tier/drift-monitor/app/schemas.py` | Pydantic schemas: DriftState, DriftEvent |
| `aiops-tier/drift-monitor/tests/test_drift.py` | Unit tests (offline, no Docker) |
| `mlops-tier/batch-orchestrator/src/mlops/drift_reference.py` | Reference artifact generator |

### Modified files

| File | Change |
|------|--------|
| `mlops-tier/batch-orchestrator/src/mlops/promotion.py` | Calls `generate_drift_reference()` after promotion |
| `infrastructure/docker-compose.yml` | Added `drift-monitor` service (profile: `drift`) |
| `infrastructure/observability/prometheus.yml` | Added `drift-monitor:7012/metrics` scrape job |
| `api-dashboard-tier/api-bff-service/main.py` | Added `/api/v1/drift/*` endpoints |
| `api-dashboard-tier/dashboard-backend/main.py` | Added `/mlops/drift*` endpoints (RBAC-gated) |
| `api-dashboard-tier/react-dashboard/src/api/mlopsApi.ts` | Added drift API functions + types |
| `api-dashboard-tier/react-dashboard/src/pages/mlops/MlopsMonitoringPage.tsx` | Added Drift Detection section |

---

## 3. Architecture Diagram

```
normalizer
  │
  └─► Redis stream:norm.telemetry
          │
          ▼
    drift-monitor (Docker Compose service, profile=drift)
          │
          ├─► feature_extractor.py
          │     ├── congestion_5g  (7 features)
          │     ├── sla_5g         (5 features)
          │     └── slice_type_5g  (6 features)
          │
          ├─► Rolling windows (500 samples per model)
          │
          ├─► alibi_detector.py (Alibi Detect MMDDrift, PyTorch backend)
          │     ├── loads /mlops/models/promoted/{model}/current/drift_reference.npz
          │     └── loads /mlops/models/promoted/{model}/current/drift_feature_schema.json
          │
          ├─► Redis hash  aiops:drift:{model_name}    (latest state)
          ├─► Redis stream events.drift               (alert events)
          ├─► Kafka topic drift.alert
          └─► InfluxDB measurement aiops_drift

    Redis aiops:drift:{model_name}
          │
          ├─► api-bff-service  GET /api/v1/drift/*
          │         │
          │         └─► dashboard-backend GET /mlops/drift* (RBAC)
          │                   │
          │                   └─► React MlopsMonitoringPage (Drift Detection section)
          │
          └─► Prometheus GET /metrics (neuroslice_drift_* gauges/counters)
```

---

## 4. Drift Event Contract

Published to `events.drift` (Redis stream) and `drift.alert` (Kafka topic):

```json
{
  "event_type": "drift.detected",
  "drift_id": "<uuid>",
  "model_name": "congestion_5g",
  "deployment_version": "3",
  "timestamp": "2024-01-01T12:00:00+00:00",
  "window_size": 500,
  "reference_sample_count": 2000,
  "p_value": 0.0042,
  "threshold": 0.01,
  "is_drift": true,
  "drift_score": 0.38,
  "feature_names": ["cpu_util_pct", "mem_util_pct", "bw_util_pct", "active_users", "queue_len", "hour", "slice_type_encoded"],
  "top_shifted_features": [],
  "severity": "HIGH",
  "recommendation": "Run offline MLOps pipeline and compare candidate model quality gates. Review feature distribution shift for congestion_5g. Do not auto-promote without operator review.",
  "auto_trigger_enabled": false,
  "scenario_b_live_mode": true
}
```

**Severity mapping:**

| p-value      | Severity  |
|-------------|-----------|
| p < 0.001   | CRITICAL  |
| p < 0.005   | HIGH      |
| p < 0.01    | MEDIUM    |
| p ≥ 0.01    | NONE      |

---

## 5. How Reference Artifacts Are Generated

When the MLOps pipeline promotes a model (`promote_onnx_artifacts` in `promotion.py`), it now also calls `generate_drift_reference()`:

1. Loads `data/processed/{model_name}_processed.npz` (X_train)
2. For `congestion_5g`: takes the last timestep of each sequence (shape `[n, 30, 7]` → `[n, 7]`), inverse-transforms via `preprocessor_congestion_5g.pkl`
3. For `sla_5g`: loads `X_train` (scaled), inverse-transforms via `scaler_sla_5g.pkl`
4. For `slice_type_5g`: loads `X_train` (unscaled, no scaler needed)
5. Samples up to 2000 rows with seed=42
6. Writes `drift_reference.npz` (key: `x_ref`) and `drift_feature_schema.json`

**If training data is unavailable** (e.g. Scenario B default without running `make pipeline`), the function returns `status=missing_training_data` and the drift-monitor reports `reference_missing` — it does **not** crash the platform.

**Expected artifact locations:**

```
mlops-tier/batch-orchestrator/models/promoted/congestion_5g/current/drift_reference.npz
mlops-tier/batch-orchestrator/models/promoted/congestion_5g/current/drift_feature_schema.json
mlops-tier/batch-orchestrator/models/promoted/sla_5g/current/drift_reference.npz
mlops-tier/batch-orchestrator/models/promoted/sla_5g/current/drift_feature_schema.json
mlops-tier/batch-orchestrator/models/promoted/slice_type_5g/current/drift_reference.npz
mlops-tier/batch-orchestrator/models/promoted/slice_type_5g/current/drift_feature_schema.json
```

To generate references without running the full MLOps pipeline:

```bash
cd neuroslice-platform/mlops-tier/batch-orchestrator
python -m src.mlops.drift_reference models/promoted data/processed
```

---

## 6. How to Run It

### Start with drift detection

```bash
cd neuroslice-platform/infrastructure
docker compose --profile drift up --build
```

### Start without drift detection (default)

```bash
cd neuroslice-platform/infrastructure
docker compose up --build
```

The drift-monitor is behind the `drift` profile because `alibi-detect[torch]` includes PyTorch which significantly increases image build time and size.

---

## 7. How to Verify It

```bash
# 1. Validate compose config
docker compose --profile drift config

# 2. Start all services
docker compose --profile drift up --build -d

# 3. Check service status
docker compose --profile drift ps

# 4. Drift-monitor health
curl http://localhost:7012/health
# Expected: {"status":"ok"|"degraded", "models":{...}}

# 5. Latest drift state per model
curl http://localhost:7012/drift/latest
# Expected: {"models":{"congestion_5g":{...},"sla_5g":{...},"slice_type_5g":{...}}}

# 6. BFF drift endpoint (public, no auth)
curl http://localhost:8000/api/v1/drift/latest

# 7. Dashboard drift endpoint (requires JWT)
curl -H "Authorization: Bearer <token>" http://localhost:8008/api/dashboard/mlops/drift

# 8. Prometheus targets (drift-monitor should appear)
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="drift-monitor")'

# 9. Prometheus metrics
curl http://localhost:7012/metrics | grep neuroslice_drift
```

### Verify reference missing state

If the MLOps pipeline has never run (default Scenario B):

```bash
curl http://localhost:7012/drift/latest | jq '.models.congestion_5g.status'
# Expected: "reference_missing"
```

### Generate reference artifacts manually

```bash
# Inside the mlops-worker container or locally if deps available:
docker compose --profile mlops run --rm mlops-worker python -m src.mlops.drift_reference models/promoted data/processed

# Then restart drift-monitor to reload
docker compose --profile drift restart drift-monitor
```

---

## 8. Test Results

Run unit tests (no Docker required):

```bash
cd neuroslice-platform
pip install pytest numpy pydantic
pip install alibi-detect[torch]   # optional; tests skip if unavailable
pytest aiops-tier/drift-monitor/tests/test_drift.py -v
```

Tests covered:
- Feature extraction produces stable numeric vectors matching schemas (all 3 models)
- Missing reference returns `reference_missing` status
- Alibi Detect detects synthetic shifted distribution (mean=0 vs mean=5)
- Same distribution produces no drift (or very low false positive rate)
- Drift event schema serialization with all required fields
- Redis state payload format and DriftStore.save_state()
- BFF drift endpoint returns valid empty response when Redis is empty

---

## 9. Current Limitations

1. **Reference artifacts require MLOps pipeline**: The drift-monitor reports `reference_missing` until `make pipeline` is run and models are promoted with drift references. This is expected behavior in Scenario B.

2. **No auto-trigger by default**: `DRIFT_AUTO_TRIGGER_MLOPS=false`. Setting it to `true` will call the MLOps runner endpoint — this is partially implemented and guarded by the existing `MLOPS_PIPELINE_ENABLED` flag.

3. **`drift` Docker Compose profile**: The service is not started by default (`docker compose up`). Use `docker compose --profile drift up` to include it. This avoids adding the large PyTorch image to the default runtime for users who do not need drift detection.

4. **Prometheus scrape target optional**: The Prometheus config includes the `drift-monitor:7012/metrics` scrape job, but Prometheus will silently fail to scrape if the service is not running.

5. **No per-model sidecar split yet**: All three models are monitored by a single service. The code is structured so that splitting into sidecars later requires only Dockerfile/compose changes.

6. **Top shifted features not populated**: `top_shifted_features` is always empty. MMD tests the joint distribution; feature-level attribution would require additional per-feature univariate tests.

---

## 10. Misrouting Exclusion

Misrouting detection (classifying whether a session is on the correct slice) remains **excluded** from this implementation per the Scenario B scope. The drift-monitor only monitors input-feature distributions for the three AIOps models: `congestion_5g`, `sla_5g`, and `slice_type_5g`.
