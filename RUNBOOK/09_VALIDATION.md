# 09 Validation

## A. Source-based validation (Copilot/Reviewer)
Use source inspection to validate architecture coherence before runtime checks.

### A.1 Compose wiring
Validate in `neuroslice-platform/infrastructure/docker-compose.yml`:
- service names and profiles
- port exposure (`ports` vs `expose`)
- stream/topic env vars
- model env vars (`MODEL_NAME`)
- volume mounts (`/mlops/models:ro`)
- `MLOPS_RUNNER_TOKEN` wiring across services

### A.2 Data-flow contracts
Validate in source:
- simulators publish to adapters
- adapters publish `stream:raw.ves` / `stream:raw.netconf`
- normalizer publishes `stream:norm.telemetry`, Kafka `telemetry-norm`, Redis entity state
- AIOps emits expected `events.*` streams
- control tier consumes/emits `stream:control.*`

### A.3 Model contracts
Validate in AIOps + MLOps source:
- model load path points to `models/promoted/{model}/current/model_fp16.onnx`
- `metadata.json` read + hot-reload logic
- fallback behavior explicit (not silent)
- training/preprocessing scripts exist for required models
- promotion writes expected `current/` artifacts and updates registry

### A.4 API/dashboard contracts
Validate:
- protected routes under `/api/dashboard/*`
- Kong routes point to `auth-service` + `dashboard-backend`
- React routes and role guards match backend roles
- MLOps and controls pages call protected dashboard APIs
- runtime control routes exist (`/api/dashboard/runtime/*`)
- evaluation routes exist (`/api/v1/evaluation/*`, `/api/dashboard/mlops/evaluation*`)

### A.5 Drift/control/security contracts
Validate:
- `aiops-drift-monitor` (Alibi MMD + reference artifacts)
- `mlops-drift-monitor` trigger path to `mlops-runner`
- `mlops-runner` action allowlist and token gate
- control-tier deterministic lifecycle and simulated execution

### A.6 Source-level E2E tests
Run contract tests without containers:

```bash
cd neuroslice-platform
pytest tests/e2e_source -q
```

## B. Runtime validation (optional human)
These checks are optional and should be executed by an operator in a running environment.

### B.1 Health checks
- Confirm key endpoints return healthy/degraded states as expected
- Confirm protected endpoints require valid auth token

### B.2 UI checks
- Login works through Kong
- Dashboard pages load by role
- Predictions, MLOps, drift, and control pages render expected data/errors

### B.3 Pipeline checks
- Trigger MLOps pipeline from Operations page
- Verify run history appears in pipeline run list
- Verify logs are present and redacted/truncated

### B.4 Drift checks
- `drift` profile: verify `aiops-drift-monitor` `/health`, `/drift/latest`, `/metrics`
- lightweight monitor: verify drift status/events endpoints via dashboard backend control proxy

### B.5 Control checks
- Validate action lifecycle transitions (`PENDING_APPROVAL -> APPROVED -> EXECUTED_SIMULATED`)

## Evidence handling
Capture:
- Compose config snapshot (`docker compose config`)
- endpoint responses
- role-based UI screenshots
- pipeline run IDs and logs
