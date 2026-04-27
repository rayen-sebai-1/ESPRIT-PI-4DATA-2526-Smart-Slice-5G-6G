# MLOps Runner

Internal-only worker that executes a single fixed offline MLOps pipeline command on demand. It exists so the React dashboard can trigger the offline training pipeline without giving any other service direct access to the Docker socket or arbitrary shell commands.

## Security model

- The command is fixed at runtime from `MLOPS_PIPELINE_COMMAND`. The runner never accepts a command, args, or shell string from its caller.
- Subprocess spawn uses an argv list (`shlex.split`) to avoid shell injection.
- The runner is bound to the internal Compose network only (no published port).
- A shared bearer token (`MLOPS_RUNNER_TOKEN`) gates the runner so only `dashboard-backend` can call it.
- A kill switch (`MLOPS_PIPELINE_ENABLED=false`) immediately disables `POST /run-pipeline` and returns `409`.
- Output is truncated to ~200 KB before returning to avoid memory blowups on long runs.

## Endpoints

- `GET /health` -> `{ status, service, enabled, command_label }`
- `POST /run-pipeline` -> blocks until the command completes (or hits `MLOPS_PIPELINE_TIMEOUT_SECONDS`), then returns `{ exit_code, duration_seconds, stdout, stderr, timed_out }`.

`dashboard-backend` calls `POST /run-pipeline` from a background task so the HTTP request from the React dashboard returns immediately with a `RUNNING` status.

## Environment variables

- `MLOPS_PIPELINE_ENABLED` (default `false`) - kill switch
- `MLOPS_PIPELINE_COMMAND` (default `docker compose --profile mlops --profile mlops-worker run --rm mlops-worker`)
- `MLOPS_PIPELINE_WORKDIR` (default `/workspace`)
- `MLOPS_PIPELINE_TIMEOUT_SECONDS` (default `7200`)
- `MLOPS_RUNNER_TOKEN` (optional shared secret matched by dashboard-backend)
