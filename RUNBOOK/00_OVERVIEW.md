# Scenario B Runbook Overview

## Purpose
This runbook is the operational and validation guide for **Scenario B** of NeuroSlice: a **local Docker Compose PoC**.

It is designed for:
- New engineers onboarding to the platform
- Reviewers validating architecture/wiring from source
- Operators preparing and running demos

## Scenario B definition
Scenario B is the integrated local platform started from:

- `neuroslice-platform/infrastructure/docker-compose.yml`

It focuses on end-to-end behavior across simulation, ingestion, AIOps (except deferred misrouting detector), control, dashboard/API, observability, and MLOps integration.

## Scope
### Included
- `simulation-tier`
- `ingestion-tier`
- `aiops-tier` (`congestion-detector`, `sla-assurance`, `slice-classifier`, optional `aiops-drift-monitor`)
- `control-tier`
- `api-dashboard-tier`
- `mlops-tier` (`batch-orchestrator`, `mlops-runner`, `mlops-drift-monitor`)
- `infrastructure` and observability assets

### Excluded now
- `agentic-ai-tier` (out of current operational scope)
- `misrouting-detector` (deferred/future)

### Not required for Scenario B
- Kubernetes
- Istio
- vLLM

## High-level architecture summary
```text
simulators -> ingestion adapters -> normalizer -> stream:norm.telemetry
            -> Kafka telemetry-norm -> InfluxDB telemetry

stream:norm.telemetry -> AIOps workers -> events.anomaly / events.sla / events.slice.classification
prediction streams + stream:norm.telemetry -> online-evaluator -> events.evaluation
AIOps events -> alert-management -> stream:control.alerts -> policy-control -> stream:control.actions
approved actions -> Redis simulation actuator keys + stream:control.actuations

Redis state + streams -> api-bff-service -> dashboard-backend (protected via Kong + auth)
dashboard-backend -> Redis runtime flags runtime:service:{name}:*

dashboard-backend -> mlops-runner (internal-only) -> offline pipeline actions
```

## Operational guardrails
- Closed-loop control is simulated only (Redis actuation keys consumed by simulators).
- No real PCF/NMS integration is called in Scenario B.

## Runbook map
- [Setup](./01_SETUP.md)
- [Startup profiles](./02_STARTUP.md)
- [Dashboard operation](./03_DASHBOARD.md)
- [Data flow contracts](./04_DATA_FLOW.md)
- [MLOps lifecycle](./05_MLOPS.md)
- [Drift systems](./06_DRIFT.md)
- [Control tier](./07_CONTROL.md)
- [Observability](./08_OBSERVABILITY.md)
- [Validation](./09_VALIDATION.md)
- [Troubleshooting](./10_TROUBLESHOOTING.md)
- [Security](./11_SECURITY.md)
- [Limitations](./12_LIMITATIONS.md)
- [Operator checklist](./13_OPERATOR_CHECKLIST.md)
