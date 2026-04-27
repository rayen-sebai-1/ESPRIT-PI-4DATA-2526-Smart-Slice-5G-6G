# Control Tier

Last verified: 2026-04-27.

The NeuroSlice Control Tier is a deterministic, human-in-the-loop control layer. It does not call any LLM, agent framework, Ollama, OpenAI API, PCF, NMS, or real remediation system. LLM usage remains limited to the existing `agentic-ai-tier` root-cause and copilot services.

## Services

### Alert Management

Path: `control-tier/alert-management`

Alert Management consumes AIOps event streams, normalizes events into structured alerts, deduplicates repeated active alerts, stores alert state in Redis, and publishes alert lifecycle events.

Inputs:

- `events.anomaly`
- `events.sla`
- `events.slice.classification`

Outputs:

- `stream:control.alerts`

Redis state:

- `control:alerts:{alert_id}` hash
- `control:alerts:index` set
- `control:alerts:dedup:{entity_id|alert_type|source}` string

APIs:

- `GET /health`
- `GET /alerts`
- `GET /alerts/{alert_id}`
- `POST /alerts/{alert_id}/acknowledge`
- `POST /alerts/{alert_id}/resolve`

Repeated events update an existing `OPEN` or `ACKNOWLEDGED` alert with the same dedup key. After an alert is resolved, a future event can create a new alert.

### Policy Control

Path: `control-tier/policy-control`

Policy Control consumes structured alerts, applies deterministic rules, stores recommended actions, and exposes operator approval/rejection/execution APIs. Execution is simulated only.

Inputs:

- `stream:control.alerts`

Outputs:

- `stream:control.actions`

Redis state:

- `control:actions:{action_id}` hash
- `control:actions:index` set
- `control:actions:by_alert:{alert_id}` string

APIs:

- `GET /health`
- `GET /actions`
- `GET /actions/{action_id}`
- `POST /actions/{action_id}/approve`
- `POST /actions/{action_id}/reject`
- `POST /actions/{action_id}/execute`

## Deterministic Policy Rules

Policy Control applies only these rules:

- `CONGESTION` with `HIGH` or `CRITICAL` severity: `RECOMMEND_PCF_QOS_UPDATE`, `MEDIUM` risk, approval required.
- `SLA_RISK` with `CRITICAL` severity: `RECOMMEND_REROUTE_SLICE`, `HIGH` risk, approval required.
- `SLA_RISK` with `HIGH` severity: `INVESTIGATE_CONTEXT`, `MEDIUM` risk, approval required.
- `SLICE_MISMATCH`: `RECOMMEND_INSPECT_SLICE_POLICY`, `LOW` risk, approval required.
- `FAULT_EVENT`: `INVESTIGATE_CONTEXT`, `LOW` risk, approval required.
- Any unmatched alert: `NO_ACTION`, `LOW` risk, no approval required, marked `EXECUTED_SIMULATED`.

The control tier has no model inference, prompt construction, semantic search, tool-calling agent loop, or generative decision path. All recommendations are rule based and reproducible.

## Human-In-The-Loop Safety

All matching remediation recommendations start as `PENDING_APPROVAL`. Operators must explicitly approve an action before it can be executed.

Lifecycle:

1. Alert arrives on `stream:control.alerts`.
2. Policy Control creates or updates one action for the unresolved alert.
3. Operator calls `POST /actions/{action_id}/approve` or `POST /actions/{action_id}/reject`.
4. `POST /actions/{action_id}/execute` works only after approval.
5. Execution sets status to `EXECUTED_SIMULATED` and publishes an update to `stream:control.actions`.

Execution never calls a real PCF, NMS, orchestrator, or network API.

## Smoke Test

Start the services:

```bash
cd neuroslice-platform/infrastructure
docker compose up --build redis alert-management policy-control
```

Inject an event:

```bash
docker compose exec redis redis-cli XADD events.anomaly "*" entity_id gnb-01-cell-01 source congestion-detector alert_type CONGESTION severity HIGH summary "High congestion detected"
```

Verify alerts and actions:

```bash
curl http://localhost:7010/health
curl http://localhost:7010/alerts
curl http://localhost:7011/health
curl http://localhost:7011/actions
```

Approve and execute one action:

```bash
curl -X POST http://localhost:7011/actions/{action_id}/approve
curl -X POST http://localhost:7011/actions/{action_id}/execute
```

The final action status must be `EXECUTED_SIMULATED`.
