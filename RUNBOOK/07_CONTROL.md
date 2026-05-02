# 07 Control Tier

## Components
- `alert-management` (ingests AIOps events -> lifecycle alerts)
- `policy-control` (ingests control alerts -> deterministic actions)

## Alert-management logic
Inputs:
- `events.anomaly`
- `events.sla`
- `events.slice.classification`

Behavior:
- Normalize incoming events to alert schema
- Deduplicate unresolved alerts using key: `entity_id|alert_type|source`
- Persist lifecycle in Redis (`control:alerts:*`)
- Publish lifecycle updates to `stream:control.alerts`

## Policy-control logic
Input:
- `stream:control.alerts`

Behavior:
- Ignore resolved alerts
- Apply deterministic policy rules
- Persist one action per alert context (`control:actions:*`)
- Publish to `stream:control.actions`
- On execute, apply Redis simulation actuations and publish `stream:control.actuations`

## Alert lifecycle
Typical states:
- `OPEN`
- `ACKNOWLEDGED`
- `RESOLVED`

APIs include acknowledge/resolve operations.

## Action lifecycle
Typical states:
- `PENDING_APPROVAL`
- `APPROVED`
- `REJECTED`
- `EXECUTED_SIMULATED`

APIs include approve/reject/execute operations.
Additional read APIs:
- `GET /actuations`
- `GET /actuations/{action_id}`

## Human-in-the-loop model
- Recommendations are created deterministically
- Operators explicitly approve or reject
- Execute endpoint records outcome as simulated

## Explicit limitation
Scenario B control execution is **simulated only**.

No real integration to:
- PCF
- NMS
- live orchestrators
- production network control planes

Actuation effect is implemented through Redis keys consumed by simulators:
- `control:sim:qos_boost`
- `control:sim:reroute_bias`
- `control:sim:edge_capacity_boost`
