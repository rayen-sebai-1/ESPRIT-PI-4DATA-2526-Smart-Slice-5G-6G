# 13 Operator Checklist

## Before demo
- Confirm required ports are free.
- Confirm expected profile choice:
  - default
  - `mlops`
  - `drift`
  - combined
- Confirm admin credentials and role test users are available.
- Confirm promoted model artifacts exist for:
  - `congestion_5g`
  - `sla_5g`
  - `slice_type_5g`
- Confirm dashboard provider is `bff`.

## During demo
- Verify health endpoints and dashboard login.
- Show live-state population from simulator-driven telemetry.
- Show predictions page (live read behavior).
- Show control actions lifecycle and simulated execute.
- Show MLOps Operations Center tool links and health.
- Trigger pipeline run (authorized role only) and show run history/logs.
- Show runtime service control cards (`/mlops/orchestration`) and toggle one service safely.
- Show online evaluation panel (`/mlops/monitoring`) and note pseudo-ground-truth availability.
- If drift profile enabled, show drift endpoints/views and metrics.

## After demo
- Collect logs and screenshots.
- Record run IDs for MLOps pipeline operations.
- Capture any fallback-mode occurrences and root cause.
- Document unresolved warnings/errors and profile used.

## Evidence to collect
- Compose command used and selected profiles
- Key endpoint responses (`/health`, protected API samples)
- Dashboard screenshots by page:
  - live-state
  - predictions
  - mlops operations/drift
  - control/actions
- Pipeline run record + redacted logs
- Drift status/events evidence (if enabled)
- Runtime control update evidence (`runtime:service:*` state snapshot)
- Online evaluation metrics evidence (`aiops:evaluation:*` or dashboard screenshot)
