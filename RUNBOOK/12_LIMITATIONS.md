# 12 Limitations

## Scope limitations
- `misrouting-detector` is deferred/future work
- `agentic-ai-tier` is out of current Scenario B run scope

## Platform limitations
- Scenario B is Docker Compose PoC, not Kubernetes/Istio deployment
- control-tier execution is simulated (no real PCF/NMS integration)
- runtime model-backed inference depends on promoted artifacts existing locally
- runtime control flags enable/disable processing logic but do not start/stop containers

## Provider/runtime limitations
- `dashboard-backend` default `bff` provider is read-oriented for predictions in live mode
- ad-hoc prediction rerun/batch can return explicit `422` in live mode

## Drift limitations
- two drift systems coexist with different purposes; operators must interpret each correctly
- Alibi statistical drift requires reference artifacts and optional `drift` profile

## Evaluation limitations
- Online evaluator uses Scenario B pseudo-ground-truth derived from simulated telemetry/fault context; it is not production-labeled truth.
