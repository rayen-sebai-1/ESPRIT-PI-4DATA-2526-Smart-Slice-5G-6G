# MLOps Runner

Internal-only worker that executes fixed offline MLOps pipeline actions on demand. It exists so the React dashboard and the drift-monitor can trigger the offline training pipeline without giving any other service direct access to the Docker socket or arbitrary shell commands.

## Security model

- Accepted actions are drawn from a fixed `_ACTION_MAP`; callers supply a key (e.g. `full_pipeline`) and cannot inject arbitrary commands or shell strings.
- Subprocess spawn uses an argv list (`["docker", "exec", container, "make", target]`) — no shell interpolation.
- The runner is bound to the internal Compose network only (no published port).
- A shared bearer token (`MLOPS_RUNNER_TOKEN`) gates the runner so only authorized services can call it.
- A kill switch (`MLOPS_PIPELINE_ENABLED=false`) immediately disables `POST /run-action` and returns `409`.
- Output is truncated to ~200 KB before returning to avoid memory blowups on long runs.

## Endpoints

- `GET /health` -> `{ status, service, enabled }`
- `POST /run-action` -> blocks until the action completes (or hits `MLOPS_ORCHESTRATION_TIMEOUT_SECONDS`), then returns `{ accepted, exit_code, duration_seconds, stdout, stderr, command_label, trigger_source, timed_out }`.

`dashboard-backend` calls `POST /run-action` from a background task so the HTTP request from the React dashboard returns immediately with a `RUNNING` status. `drift-monitor` calls it directly when an anomaly burst is detected.

## Request body

```json
{
  "action": "full_pipeline",
  "trigger_source": "manual",
  "parameters": {}
}
```

- `action`: one of the keys in `_ACTION_MAP` (see below)
- `trigger_source`: `manual` | `drift` | `scheduled` (default `manual`)
- `parameters`: optional `{ KEY: value }` pairs appended as `KEY=value` to the make target; keys are validated against `^[A-Za-z0-9_]+$`

## Action map

| Action key | Make target |
|---|---|
| `prepare_data` | `prepare-data` |
| `validate_data` | `validate-data` |
| `train` | `train` |
| `evaluate` | `evaluate` |
| `log_mlflow` | `log-mlflow` |
| `export_onnx` | `export-onnx` |
| `convert_fp16` | `convert-fp16` |
| `validate_model` | `validate-model` |
| `promote_model` | `promote-model` |
| `rollback_model` | `rollback-model` |
| `full_pipeline` | `mlops-full` |

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `MLOPS_ORCHESTRATION_ENABLED` | `true` | Kill switch — set `false` to return 409 on all run requests |
| `MLOPS_ORCHESTRATION_WORKDIR` | `/workspace/neuroslice-platform/infrastructure` | Working directory for subprocess |
| `MLOPS_ORCHESTRATION_TIMEOUT_SECONDS` | `7200` | Max seconds before the subprocess is killed |
| `MLOPS_RUNNER_TOKEN` | *(unset)* | Optional shared bearer token; if set, all callers must include `Authorization: Bearer <token>` |
| `MLOPS_API_CONTAINER_NAME` | *(auto-detected)* | Override the mlops-api container name; auto-detected via `docker ps` label if unset |
