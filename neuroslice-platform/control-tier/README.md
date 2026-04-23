# Control Tier

Control and closed-loop automation tier for turning detections into actions.

## Tier Purpose

This tier is intended to host policy decisions and remediation workflows that act on events coming from AIOps and operations APIs.

Planned responsibilities:

- Evaluate remediation policies based on severity, domain, and slice impact.
- Manage alert lifecycle and escalation.
- Trigger corrective actions (traffic steering, scaling, policy updates).
- Keep auditable action history and rollback context.

## Current Status

This tier is scaffold-only for now.

Available directories:

- `alert-management/`
- `policy-control/`

No runnable services or APIs are currently implemented in this tier.

## Recommended Interface Contracts (Target)

Suggested inputs:

- Redis/Kafka AIOps streams (`events.anomaly`, `events.sla`, `events.slice.classification`)
- Fault/scenario context from API BFF or fault-engine

Suggested outputs:

- Action stream for applied decisions (e.g., `stream:control.actions`)
- Alert stream for NOC/UI consumption (e.g., `stream:alerts`)
- Optional northbound API endpoints for manual approval/override

## Suggested MVP Roadmap

1. Implement `alert-management` service for deduplication, severity normalization, and routing.
2. Implement `policy-control` service with rule engine and dry-run mode.
3. Add audit persistence for actions and policy decisions.
4. Connect outcomes into `api-dashboard-tier` for operator visibility.

## Folder Map

```text
control-tier/
├── alert-management/
└── policy-control/
```
