# Control Tier

The control tier is intended to host closed-loop automation, remediation policy execution, and operator action workflows driven by NeuroSlice events.

## Current Status

This tier is scaffold-only in the current repository state.

- No service directories are committed under `control-tier/`
- No Docker Compose services are defined for this tier in `infrastructure/docker-compose.yml`
- No alert-management API, policy engine, or action worker is implemented yet

Today, the folder contains only this file.

## Expected Upstream Inputs

When implemented, this tier would most likely consume:

- normalized telemetry from `stream:norm.telemetry`
- AIOps output streams:
  - `events.anomaly`
  - `events.sla`
  - `events.slice.classification`
- active fault state from `faults:active`
- dashboard/API workflows from `api-dashboard-tier`

## Possible Future Outputs

- action or remediation streams for downstream automation
- alert lifecycle state for operators
- approval and override APIs for human-in-the-loop workflows
- audit logs for policy decisions and corrective actions

## Documentation Note

Older documentation may mention folders such as `alert-management/` or `policy-control/`. Those directories are not present in the current workspace.

## Folder Map

```text
control-tier/
`-- README.md
```
