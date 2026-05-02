# SOURCE_VALIDATION_REPORT

Date: 2026-04-30  
Validation mode: **source-code only** (no runtime execution claims)

Note: **Runbook folder created** at `RUNBOOK/` with structured Scenario B operational documentation.

## Executive summary
Scenario B (Docker Compose local PoC) is largely implemented and wired, with key flows present across simulation, ingestion, AIOps, control, dashboard/API, and MLOps. The core architecture is coherent, but there are important gaps that keep full compliance from PASS:

- Observability coverage is incomplete (Prometheus targets + missing `/metrics` in critical services).
- Two AIOps workers (`sla-assurance`, `slice-classifier`) still allow legacy non-ONNX runtime fallback paths when promoted ONNX is unavailable.
- Live `bff` provider supports read paths, but prediction rerun/batch actions are intentionally blocked (`422`) in live mode.
- Security posture is partially dev-oriented (browser-exposed MLOps UIs and docker-socket usage in runner by design).

## Scope exclusions
- `agentic-ai-tier`: **out of current validation scope**.
- `misrouting-detector`: **deferred/future work**, not required for current Scenario B validation.

## Validation matrix
| Area | Expected | Source files checked | Status: PASS/PARTIAL/FAIL | Evidence | Required fix |
|---|---|---|---|---|---|
| End-to-end ingestion flow | `simulator-core/simulator-ran -> adapter-ves -> stream:raw.ves` and `simulator-edge -> adapter-netconf -> stream:raw.netconf` | `simulation-tier/simulator-core/engine.py`, `simulation-tier/simulator-ran/engine.py`, `simulation-tier/simulator-edge/engine.py`, `ingestion-tier/adapter-ves/main.py`, `ingestion-tier/adapter-netconf/main.py`, `ingestion-tier/shared/config.py` | PASS | Simulators POST to `/events` or `/telemetry`; adapters publish `cfg.stream_raw_ves` / `cfg.stream_raw_netconf`. | None |
| Normalization + fan-out | `normalizer -> stream:norm.telemetry + Kafka telemetry-norm + Redis entity state` | `ingestion-tier/normalizer/main.py`, `ingestion-tier/shared/redis_client.py`, `infrastructure/docker-compose.yml` | PASS | `publish_to_stream(...stream_norm_telemetry...)`, `producer.send_and_wait(KAFKA_TOPIC)`, `set_entity_state(entity:{id})`. | None |
| AIOps event outputs | Workers emit `events.anomaly`, `events.sla`, `events.slice.classification` | `aiops-tier/*/config.py`, `aiops-tier/*/publisher.py`, `infrastructure/docker-compose.yml` | PASS | Compose sets `OUTPUT_STREAM` and Kafka topics; publishers include fallback state in output payloads. | None |
| Control flow chain | `alert-management -> stream:control.alerts`, `policy-control -> stream:control.actions` | `control-tier/alert-management/app/config.py`, `alert_store.py`, `policy-control/app/config.py`, `action_store.py` | PASS | Alert store publishes lifecycle events to configured output stream; policy store publishes action lifecycle to `stream:control.actions`. | None |
| Dashboard views data path | `api-bff-service` + `dashboard-backend` + React routes for national/region/sessions/predictions | `api-dashboard-tier/dashboard-backend/main.py`, `providers/bff.py`, `react-dashboard/src/app/router.tsx`, `api-dashboard-tier/api-bff-service/main.py` | PARTIAL | National/region/sessions/predictions list/detail are implemented in `bff` provider; rerun/batch are explicit `422` in live mode, not `501`. | If live-mode rerun/batch is required, implement server-side action path (currently intentionally read-oriented). |
| AIOps model names (Compose) | `congestion_5g`, `sla_5g`, `slice_type_5g` | `infrastructure/docker-compose.yml` | PASS | `MODEL_NAME` set correctly on each AIOps worker. | None |
| AIOps promoted artifact contract | Load `/mlops/models/promoted/{MODEL_NAME}/current/model_fp16.onnx` + `metadata.json`; support hot reload | `aiops-tier/shared/model_hot_reload.py`, `congestion-detector/main.py`, `sla-assurance/main.py`, `slice-classifier/main.py`, loaders | PARTIAL | Shared resolver points to promoted `current/model_fp16.onnx` + `metadata.json`; hot reload via `should_reload_promoted_model(...)`. | Remove legacy runtime fallbacks from `sla-assurance` and `slice-classifier` for strict ONNX-only production policy. |
| Fallback visibility | Fallback mode explicit in outputs/state/logs | `aiops-tier/*/inference.py`, `aiops-tier/*/publisher.py`, loaders | PASS | `fallbackMode` propagated; loaders log `model_format`, `fallback_mode`, source. | None |
| No silent legacy `.pt` production usage | No hidden fallback to old PyTorch `.pt` runtime | `aiops-tier/congestion-detector/model_loader.py`, `sla-assurance/model_loader.py`, `slice-classifier/model_loader.py` | PARTIAL | `congestion-detector` is ONNX/heuristic only; `sla` + `slice` still allow `legacy_local_artifact` and local registry fallback. | Remove legacy local/registry fallbacks for production runtime strictness. |
| MLOps preprocessing/training coverage | preprocessing + training scripts for `congestion_5g`, `sla_5g`, `slice_type_5g`, MLflow logging | `mlops-tier/batch-orchestrator/src/data/preprocess_*.py`, `src/models/train_*.py` | PASS | Required scripts exist; training scripts use `mlflow.start_run`, `mlflow.log_*`, `mlflow.register_model`. | None |
| ONNX + FP16 + promotion outputs | ONNX export, FP16 conversion, promotion writes full `current/` bundle, updates registry | `src/mlops/onnx_export.py`, `src/mlops/promotion.py`, `src/models/lifecycle.py`, tests | PARTIAL | ONNX export + FP16 conversion + validation exist; promotion writes `model_fp16.onnx`, `metadata.json`, `version.txt`; drift artifacts generated post-promotion. | Drift artifact generation is non-fatal; enforce hard failure if strict artifact completeness is required before promotion success. |
| Quality gates before promotion | Promotion uses quality checks | `src/models/lifecycle.py` (`evaluate_promotion`, `_refresh_promotions`) | PASS | Entries require `quality_gate_status=pass` to become `promoted`/`production`. | None |
| Runtime mount policy | AIOps services mount promoted artifacts read-only | `infrastructure/docker-compose.yml` | PASS | `../mlops-tier/batch-orchestrator/models:/mlops/models:ro` (+ data/src ro) on AIOps services. | None |
| Scenario B Alibi drift monitor | MMD, window/p-threshold configurable, reference/schema load, Redis state, events, Kafka, metrics | `aiops-tier/drift-monitor/app/main.py`, `alibi_detector.py`, `config.py`, `drift_store.py`, `consumer.py` | PASS | Uses `MMDDrift`; defaults `DRIFT_WINDOW_SIZE=500`, `DRIFT_P_VALUE_THRESHOLD=0.01`; loads `drift_reference.npz` + `drift_feature_schema.json`; writes `aiops:drift:*`; emits `events.drift` + Kafka `drift.alert`; exposes `/metrics`. | None |
| Lightweight drift monitor | Trigger MLOps runner with `trigger_source=drift`; clearly separated from Alibi MMD monitor | `mlops-tier/drift-monitor/main.py`, `infrastructure/docker-compose.yml`, `mlops-tier/README.md`, `infrastructure/README.md` | PASS | Lightweight monitor counts anomaly bursts and calls `mlops-runner /run-action`; docs now explicitly distinguish lightweight vs Alibi MMD monitor. | None |
| MLOps Operations Center wiring | Links/health endpoints, pipeline run endpoint, DB history, runner-only delegation | `dashboard-backend/main.py`, `mlops_ops.py`, `models.py`, `react-dashboard/src/api/mlopsApi.ts`, `MlopsOperationsPage.tsx` | PASS | `/mlops/tools`, `/mlops/tools/health`, `/mlops/pipeline/run`; history stored in `dashboard.mlops_pipeline_runs`; delegation is `POST /run-action` with fixed payload. | None |
| Runner command safety | Fixed action keys, no arbitrary shell execution | `mlops-tier/mlops-runner/main.py`, `dashboard-backend/mlops_orchestration.py` | PASS | `_ACTION_MAP` allowlist; unknown actions rejected; parameters key-pattern validated; argv-based subprocess. | None |
| Log redaction + truncation | Sensitive data redacted/truncated before store/display | `dashboard-backend/mlops_ops.py`, `mlops_orchestration.py`, `mlops-runner/main.py` | PASS | Regex redaction + truncation (`~200KB`) in backend services and runner output handling. | None |
| Role access model | `ADMIN`/`DATA_MLOPS_ENGINEER` can trigger/promote/rollback; manager read-only; operator excluded from MLOps pages | `dashboard-backend/main.py`, `react-dashboard/src/app/router.tsx` | PASS | Backend writer roles = `ADMIN`, `DATA_MLOPS_ENGINEER`; React `/mlops/*` guarded for `ADMIN`, `DATA_MLOPS_ENGINEER`, `NETWORK_MANAGER`. | None |
| Control tier behavior | consume AIOps streams, dedup alerts, lifecycle storage, deterministic actions, approve/reject/execute simulated | `control-tier/alert-management/*`, `policy-control/*` | PASS | Dedup key `entity|alert_type|source`; alert lifecycle in Redis; deterministic policy rules; execution note explicitly simulated. | None |
| Dashboard controls proxy + role coherence | Secure `/api/dashboard/controls/*` proxy and authorized UI actions | `dashboard-backend/main.py`, `react-dashboard/src/api/controlApi.ts`, `ControlActionsPage.tsx` | PASS | Backend proxy with JWT/role checks; frontend now role-gates drift API usage/trigger to avoid unauthorized calls. | None |
| Prometheus coverage | Scrape all key Scenario B services, not only adapters/drift | `infrastructure/observability/prometheus.yml` | FAIL | Current config scrapes adapters, Prometheus, optional aiops drift only. | Add scrape jobs for `congestion-detector`, `sla-assurance`, `slice-classifier`, `alert-management`, `policy-control`, `dashboard-backend`, `mlops-runner`, `mlops-drift-monitor` and implement missing `/metrics` endpoints. |
| `/metrics` endpoint coverage | `/metrics` available on required services | `aiops-tier/*`, `control-tier/*`, `dashboard-backend/*`, `mlops-tier/*`, `ingestion-tier/*` | FAIL | `@app.get('/metrics')` exists in adapters; aiops-drift uses mounted metrics; missing in major worker/control/dashboard/runner services. | Implement metrics endpoints/instrumentation for required services. |
| ELK/Grafana assets | Canonical prediction monitoring path + dashboards/provisioning | `mlops-tier/batch-orchestrator/logstash/pipeline/logstash.conf`, `infrastructure/observability/elasticsearch/*`, `kibana/*`, `grafana/provisioning/*` | PARTIAL | Assets/provisioning scripts exist; canonical schema templates exist. Source-level linkage from online AIOps workers to Logstash is not clearly end-to-end in runtime path. | Add explicit AIOps->Logstash emitter or document exact producer path used in Scenario B runtime. |
| Security/config consistency | No exposure of sensitive internals; protected dashboard traffic; token wiring; unauth pipeline trigger impossible | `infrastructure/docker-compose.yml`, `kong-gateway/kong.yml`, `dashboard-backend/security.py`, `service.py`, `mlops-runner/main.py` | PARTIAL | JWT/session/role checks are implemented; runner token gate present; pipeline trigger requires auth roles. Dev stack still publishes MLflow/MinIO/Kibana/etc host ports and runner has docker socket mount by design. | For stricter hardening: disable host publishing of internal tools by default, keep only required dev profiles, and isolate privileged runner further. |
| Documentation correctness | READMEs aligned with Scenario B Compose scope and deferred items | All repository `README.md` files (18 total) | PARTIAL | Scope/deferred sections added; multiple README inaccuracies corrected; some non-README docs required minor drift naming correction. | Keep README verification tied to Compose changes in CI doc-check step. |

## Critical gaps
1. Observability is the largest gap: incomplete Prometheus scrape coverage and missing `/metrics` for required Scenario B services.
2. `sla-assurance` and `slice-classifier` still include legacy artifact fallback paths (`legacy_local_artifact` / local registry), which weakens strict promoted-ONNX runtime guarantees.
3. Live `bff` provider is intentionally read-oriented; prediction rerun/batch remains unavailable (`422`) in live mode.
4. Security posture remains development-first in Compose (`mlops` profile host-published UIs, docker socket in runner).

## Recommended fixes
1. Add service-level metrics instrumentation for `congestion-detector`, `sla-assurance`, `slice-classifier`, `alert-management`, `policy-control`, `dashboard-backend`, `mlops-runner`, `mlops-drift-monitor`; then expand `prometheus.yml` scrape jobs.
2. Enforce ONNX-only runtime in all AIOps workers by removing legacy local/registry runtime model loading branches from `sla-assurance` and `slice-classifier`.
3. Decide explicit product behavior for live-mode prediction rerun/batch: either implement server-side action path from live data plane or keep `422` and label UI clearly as read-only in live mode.
4. Harden default security profile for Scenario B demos: avoid exposing MinIO/MLflow/Kibana unless explicitly enabled by profile/flag.
5. Add a documentation consistency check (README + Compose route/service names + env names) to CI.

## Files changed
- `SOURCE_VALIDATION_REPORT.md` (new)
- `neuroslice-platform/infrastructure/docker-compose.yml`
- `neuroslice-platform/api-dashboard-tier/dashboard-backend/main.py`
- `neuroslice-platform/api-dashboard-tier/dashboard-backend/mlops_ops.py`
- `neuroslice-platform/api-dashboard-tier/dashboard-backend/tests/test_mlops_ops_service.py`
- `README.md`
- `neuroslice-platform/README.md`
- `neuroslice-platform/infrastructure/README.md`
- `neuroslice-platform/infrastructure/observability/README.md`
- `neuroslice-platform/infrastructure/observability/prometheus.yml`
- `neuroslice-platform/ingestion-tier/README.md`
- `neuroslice-platform/control-tier/README.md`
- `neuroslice-platform/api-dashboard-tier/README.md`
- `neuroslice-platform/api-dashboard-tier/dashboard-backend/README.md`
- `neuroslice-platform/mlops-tier/README.md`
- `neuroslice-platform/simulation-tier/README.md`
- `neuroslice-platform/agentic-ai-tier/README.md`
- `neuroslice-platform/simulation-tier/simulator-edge/engine.py`
- `neuroslice-platform/simulation-tier/simulator-ran/engine.py`
- `neuroslice-platform/api-dashboard-tier/react-dashboard/src/pages/ControlActionsPage.tsx`
- `neuroslice-platform/mlops-tier/mlops-runner/main.py`
- `neuroslice-platform/SCENARIO_B_DRIFT_DETECTION.md`

## README cleanup summary
| README file | Problem found | Change made | Status |
|---|---|---|---|
| `README.md` | Scope not explicit for current validation | Added Scenario B active scope + exclusions (`agentic-ai-tier`, `misrouting-detector`) | Updated |
| `neuroslice-platform/README.md` | Scope/service naming ambiguity for drift monitors | Added explicit scope; updated drift service names | Updated |
| `neuroslice-platform/infrastructure/README.md` | Drift naming + runtime notes needed clarification | Updated service names and clarified dual drift monitors | Updated |
| `neuroslice-platform/infrastructure/observability/README.md` | Scrape target naming and coverage note needed correction | Updated target naming and explicit scrape-gap note | Updated |
| `neuroslice-platform/ingestion-tier/README.md` | Incorrect Prometheus statement in integrated stack | Corrected wording to reflect actual integrated behavior | Updated |
| `neuroslice-platform/control-tier/README.md` | Local commands mixed shell style | Replaced/standardized local env examples for bash consistency | Updated |
| `neuroslice-platform/api-dashboard-tier/README.md` | Pipeline history table naming mismatch + drift proxy naming | Corrected to `dashboard.mlops_pipeline_runs`; updated drift proxy naming | Updated |
| `neuroslice-platform/api-dashboard-tier/dashboard-backend/README.md` | Provider defaults and pipeline delegation details stale | Corrected default provider, live-mode behavior (`422`), and `/run-action` contract | Updated |
| `neuroslice-platform/mlops-tier/README.md` | Incorrect claim that lightweight drift monitor loads Alibi reference artifacts | Corrected to `aiops-drift-monitor` for Alibi artifacts; clarified lightweight vs MMD roles | Updated |
| `neuroslice-platform/simulation-tier/README.md` | Cross-simulator state key alias not documented | Added `core:active_sessions` compatibility alias | Updated |
| `neuroslice-platform/agentic-ai-tier/README.md` | Current validation scope exclusion missing | Added explicit out-of-scope note for current Scenario B validation | Updated |
| `neuroslice-platform/aiops-tier/README.md` | No blocking inconsistency found in this pass | Retained with current statements | Verified |
| `neuroslice-platform/api-dashboard-tier/react-dashboard/README.md` | No blocking inconsistency found in this pass | Retained; behavior aligns with protected route model | Verified |
| `neuroslice-platform/api-dashboard-tier/kong-gateway/README.md` | No blocking inconsistency found in this pass | Retained; route model reflects source config | Verified |
| `neuroslice-platform/api-dashboard-tier/auth-service/README.md` | No blocking inconsistency found in this pass | Retained | Verified |
| `neuroslice-platform/mlops-tier/batch-orchestrator/README.md` | No blocking inconsistency found in this pass | Retained | Verified |
| `neuroslice-platform/mlops-tier/mlops-runner/README.md` | No blocking inconsistency found in this pass | Retained | Verified |
| `neuroslice-platform/mlops-tier/batch-orchestrator/data/README.md` | No blocking inconsistency found in this pass | Retained | Verified |
