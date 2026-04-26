# Control Tier

The control tier is reserved for closed-loop automation, remediation policy execution, and operator action workflows driven by NeuroSlice events.

## Current Status

This tier is scaffold-only in the current workspace.

- no service directories are implemented under `control-tier/`
- no Compose services are defined for this tier
- no alert-management API, policy engine, action worker, or remediation executor is implemented yet

Today this folder contains only this README.

## Expected Inputs

Future control services are expected to consume:

- normalized telemetry from `stream:norm.telemetry`
- AIOps streams `events.anomaly`, `events.sla`, and `events.slice.classification`
- latest AIOps Redis state under `aiops:*`
- active fault state from `faults:active`
- operator requests from the dashboard/API stack
- root-cause and copilot recommendations from `agentic-ai-tier`

## Expected Outputs

Future outputs may include:

- remediation or intent streams
- alert lifecycle state
- approval and override APIs
- policy execution audit trails
- rollback and safety guard metadata
