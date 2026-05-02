# Control Tier

Last verified: 2026-04-29.

The Control Tier contains the deterministic operations layer for NeuroSlice. It converts AIOps prediction events into lifecycle-managed alerts, then converts unresolved alerts into operator-approved remediation recommendations.

Fault-originated alerts in Scenario B are simulator-driven test events, not real network-fault ingestion from production systems.

This tier is intentionally rule based. It does not call LLMs, agent frameworks, Ollama, OpenAI APIs, PCF, NMS, orchestrators, or any real network remediation system. Execution is simulated and recorded as state.

## Directory Layout

```text
control-tier/
|-- README.md
|-- alert-management/
|   |-- Dockerfile
|   |-- requirements.txt
|   `-- app/
|       |-- main.py
|       |-- config.py
|       |-- consumer.py
|       |-- alert_store.py
|       |-- redis_client.py
|       |-- schemas.py
|       `-- __init__.py
`-- policy-control/
    |-- Dockerfile
    |-- requirements.txt
    `-- app/
        |-- main.py
        |-- config.py
        |-- consumer.py
        |-- policy_engine.py
        |-- action_store.py
        |-- redis_client.py
        |-- schemas.py
        `-- __init__.py
```

Both services are Python 3.11 FastAPI applications backed by Redis Streams and Redis hashes. Both use the same runtime dependencies:

- `fastapi==0.111.0`
- `uvicorn[standard]==0.30.1`
- `redis==5.0.8`
- `pydantic==2.7.4`

## Services

### Alert Management

Path: `control-tier/alert-management`

Default port: `7010`

Purpose:

- Consumes AIOps Redis streams.
- Normalizes incoming prediction/fault payloads into structured alerts.
- Filters benign events when no explicit alert type is provided.
- Deduplicates repeated active alerts by `entity_id|alert_type|source`.
- Stores alert state in Redis.
- Publishes alert lifecycle events to the control alert stream.

Source files:

- `app/main.py`: FastAPI app, health endpoint, alert REST API, startup/shutdown consumer lifecycle.
- `app/config.py`: environment-backed defaults for Redis, stream, consumer, and service settings.
- `app/consumer.py`: Redis Stream consumer and event-to-alert normalization logic.
- `app/alert_store.py`: Redis-backed alert persistence, deduplication, acknowledgement, resolution, and publishing.
- `app/redis_client.py`: Redis connection, stream group, hash encoding, and event publishing helpers.
- `app/schemas.py`: alert enums and Pydantic alert model.

Input streams:

- `events.anomaly`
- `events.sla`
- `events.slice.classification`

Output stream:

- `stream:control.alerts`

Published event types:

- `alert.created`
- `alert.updated`
- `alert.acknowledged`
- `alert.resolved`

Redis state:

- `control:alerts:{alert_id}` hash
- `control:alerts:index` set
- `control:alerts:dedup:{entity_id|alert_type|source}` string

REST API:

- `GET /health`
- `GET /alerts`
- `GET /alerts/{alert_id}`
- `POST /alerts/{alert_id}/acknowledge`
- `POST /alerts/{alert_id}/resolve`

Alert statuses:

- `OPEN`
- `ACKNOWLEDGED`
- `RESOLVED`

Alert types:

- `CONGESTION`
- `SLA_RISK`
- `SLICE_MISMATCH`
- `FAULT_EVENT`
- `UNKNOWN`

Severity handling:

- Explicit string severities are accepted when they match `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`.
- Numeric severities map as `0`/`1` to `LOW`, `2` to `MEDIUM`, `3` to `HIGH`, and `4` to `CRITICAL`.
- If no severity is provided, `score`, `risk_score`, `riskScore`, or `confidence` can derive severity: `>=0.85` critical, `>=0.70` high, `>=0.50` medium, otherwise low.
- Benign predictions such as `normal` or `sla_stable`, severity `0`, and non-mismatch slice details are ignored unless an explicit `alert_type` is supplied.

### Policy Control

Path: `control-tier/policy-control`

Default port: `7011`

Purpose:

- Consumes normalized alerts from Alert Management.
- Ignores resolved alerts.
- Applies deterministic policy rules.
- Stores one action per unresolved alert.
- Lets operators approve, reject, or execute simulated actions.
- Publishes action lifecycle events to the control action stream.

Source files:

- `app/main.py`: FastAPI app, health endpoint, action REST API, startup/shutdown consumer lifecycle.
- `app/config.py`: environment-backed defaults for Redis, stream, consumer, and service settings.
- `app/consumer.py`: Redis Stream consumer for control alerts.
- `app/policy_engine.py`: deterministic alert-to-action rule engine.
- `app/action_store.py`: Redis-backed action persistence, approval, rejection, simulated execution, and publishing.
- `app/redis_client.py`: Redis connection, stream group, hash encoding, and event publishing helpers.
- `app/schemas.py`: action enums, action model, and policy decision model.

Input stream:

- `stream:control.alerts`

Output stream:

- `stream:control.actions`

Published event types:

- `action.created`
- `action.updated`
- `action.approved`
- `action.rejected`
- `action.executed_simulated`

Existing terminal actions are returned as unchanged internally and are not republished.

Redis state:

- `control:actions:{action_id}` hash
- `control:actions:index` set
- `control:actions:by_alert:{alert_id}` string
- `control:actuations:{action_id}` hash
- `control:actuations:index` set
- `control:actuation:qos:{entity_id}`
- `control:actuation:reroute:{entity_id}`
- `control:actuation:scale:{entity_id}`
- `control:actuation:inspect:{entity_id}`
- `control:actuation:investigate:{entity_id}`
- `control:sim:qos_boost`
- `control:sim:reroute_bias` and optional `control:sim:reroute_bias:{slice_id}`
- `control:sim:edge_capacity_boost` and optional `control:sim:edge_capacity_boost:{entity_id}`

REST API:

- `GET /health`
- `GET /actions`
- `GET /actions/{action_id}`
- `POST /actions/{action_id}/approve`
- `POST /actions/{action_id}/reject`
- `POST /actions/{action_id}/execute`
- `GET /actuations`
- `GET /actuations/{action_id}`

Action statuses:

- `PENDING_APPROVAL`
- `APPROVED`
- `REJECTED`
- `EXECUTED_SIMULATED`
- `FAILED`

Action types:

- `RECOMMEND_PCF_QOS_UPDATE`
- `RECOMMEND_REROUTE_SLICE`
- `RECOMMEND_SCALE_EDGE_RESOURCE`
- `RECOMMEND_INSPECT_SLICE_POLICY`
- `INVESTIGATE_CONTEXT`
- `NO_ACTION`

## Environment Variables

Alert Management defaults:

| Variable | Default |
| --- | --- |
| `SERVICE_NAME` | `alert-management` |
| `SERVICE_PORT` | `7010` |
| `REDIS_HOST` | `redis` |
| `REDIS_PORT` | `6379` |
| `REDIS_DB` | `0` |
| `INPUT_STREAMS` | `events.anomaly,events.sla,events.slice.classification` |
| `OUTPUT_STREAM` | `stream:control.alerts` |
| `CONSUMER_GROUP` | `control-alert-management-group` |
| `CONSUMER_NAME` | `alert-management-01` |
| `READ_COUNT` | `32` |
| `BLOCK_MS` | `1000` |
| `STREAM_MAXLEN` | `10000` |

Policy Control defaults:

| Variable | Default |
| --- | --- |
| `SERVICE_NAME` | `policy-control` |
| `SERVICE_PORT` | `7011` |
| `REDIS_HOST` | `redis` |
| `REDIS_PORT` | `6379` |
| `REDIS_DB` | `0` |
| `INPUT_STREAM` | `stream:control.alerts` |
| `OUTPUT_STREAM` | `stream:control.actions` |
| `CONSUMER_GROUP` | `control-policy-group` |
| `CONSUMER_NAME` | `policy-control-01` |
| `READ_COUNT` | `32` |
| `BLOCK_MS` | `1000` |
| `STREAM_MAXLEN` | `10000` |

In `infrastructure/docker-compose.yml`, both services are built from the platform root context. `alert-management` depends on healthy Redis, and `policy-control` depends on healthy Redis plus the started Alert Management service.

## Deterministic Policy Rules

| Alert condition | Action | Risk | Approval | Policy ID |
| --- | --- | --- | --- | --- |
| `CONGESTION` with `HIGH` or `CRITICAL` severity | `RECOMMEND_PCF_QOS_UPDATE` | `MEDIUM` | Required | `POLICY-CONGESTION-HIGH` |
| `SLA_RISK` with `CRITICAL` severity | `RECOMMEND_REROUTE_SLICE` | `HIGH` | Required | `POLICY-SLA-CRITICAL` |
| `SLA_RISK` with `HIGH` severity | `INVESTIGATE_CONTEXT` | `MEDIUM` | Required | `POLICY-SLA-HIGH` |
| `SLICE_MISMATCH` | `RECOMMEND_INSPECT_SLICE_POLICY` | `LOW` | Required | `POLICY-SLICE-MISMATCH` |
| `FAULT_EVENT` | `INVESTIGATE_CONTEXT` | `LOW` | Required | `POLICY-FAULT-EVENT` |
| Any unmatched alert | `NO_ACTION` | `LOW` | Not required | `POLICY-NO-MATCH` |

Unmatched alerts are immediately marked `EXECUTED_SIMULATED`. Matching remediation recommendations start as `PENDING_APPROVAL`.

## Human-In-The-Loop Lifecycle

1. AIOps publishes an event to one of the input streams.
2. Alert Management creates or updates an alert in Redis.
3. Alert Management publishes the alert to `stream:control.alerts`.
4. Policy Control creates or updates one action for each unresolved alert.
5. An operator approves or rejects the action through the REST API.
6. Approved actions can be executed through `POST /actions/{action_id}/execute`.
7. Execution records `EXECUTED_SIMULATED` and publishes an action update to `stream:control.actions`.

During execution, `policy-control` applies a Redis-only simulation actuator (`simulation_actuator.py`) and publishes a lifecycle event to `stream:control.actuations`. This closes the Scenario B control loop without contacting any external PCF/NMS API.

Rejected, executed, and failed actions are terminal. Simulated execution never calls a real PCF, NMS, orchestrator, or network API.

## Metrics

Both services expose `GET /metrics`.

Alert-management metrics:

- `neuroslice_control_alerts_total{severity,type,status}`
- `neuroslice_control_events_processed_total{service}`
- `neuroslice_control_last_event_timestamp{service}`

Policy-control metrics:

- `neuroslice_control_actions_total{action_type,status}`
- `neuroslice_control_events_processed_total{service}`
- `neuroslice_control_last_event_timestamp{service}`

## Run With Docker Compose

From the infrastructure directory:

```bash
cd neuroslice-platform/infrastructure
docker compose up --build redis alert-management policy-control
```

Health checks:

```bash
curl http://localhost:7010/health
curl http://localhost:7011/health
```

Inject a test congestion event:

```bash
docker compose exec redis redis-cli XADD events.anomaly "*" entity_id gnb-01-cell-01 source congestion-detector alert_type CONGESTION severity HIGH summary "High congestion detected"
```

Inspect alerts and actions:

```bash
curl http://localhost:7010/alerts
curl http://localhost:7011/actions
```

Approve and execute an action:

```bash
curl -X POST http://localhost:7011/actions/{action_id}/approve
curl -X POST http://localhost:7011/actions/{action_id}/execute
```

The final action status should be `EXECUTED_SIMULATED`.

## Local Development

Each service can also be run directly if Redis is reachable:

```bash
cd neuroslice-platform/control-tier/alert-management
pip install -r requirements.txt
export REDIS_HOST=localhost
uvicorn app.main:app --host 0.0.0.0 --port 7010
```

```bash
cd neuroslice-platform/control-tier/policy-control
pip install -r requirements.txt
export REDIS_HOST=localhost
uvicorn app.main:app --host 0.0.0.0 --port 7011
```
