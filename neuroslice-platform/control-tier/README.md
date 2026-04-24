# Control Tier

The control tier is intended to host closed-loop automation, remediation policy execution, and operator action workflows driven by NeuroSlice events.

## Current Status

This tier is scaffold-only in the current repository state.

- no service directories are committed under `control-tier/`
- no Compose services are defined for it in `infrastructure/docker-compose.yml`
- no alert-management API, policy engine, or action worker is implemented yet

Today, this folder contains only this README.

## Expected Upstream Inputs

- normalized telemetry from `stream:norm.telemetry`
- runtime AIOps streams `events.anomaly`, `events.sla`, and `events.slice.classification`
- active fault state from `faults:active`
- operator workflows from `api-dashboard-tier`

## Likely Future Outputs

- remediation or action streams
- alert lifecycle state
- approval and override APIs
- audit trails for automated decisions
