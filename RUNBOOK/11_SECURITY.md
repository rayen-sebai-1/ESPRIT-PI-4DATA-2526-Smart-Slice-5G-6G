# 11 Security

## JWT/session handling
- Access tokens are issued/validated by auth/dashboard services.
- `dashboard-backend` validates token claims and active session records before serving protected routes.

## Kong vs backend validation
- Kong primarily handles routing/CORS/rate-limits.
- Token and role enforcement is performed in backend services.

## Secret exposure risks (Scenario B dev mode)
- Local defaults exist for convenience in Compose.
- `mlops` profile publishes MLflow/MinIO/Kibana/Elasticsearch to host.
- These defaults are not production-safe.

## `mlops-runner` security model
- Internal service only (not host published)
- Requires fixed action keys (allowlist)
- Optional bearer token gate (`MLOPS_RUNNER_TOKEN`)
- No arbitrary command execution accepted from request body

## Docker socket restriction
`mlops-runner` mounts Docker socket by design to orchestrate offline tasks.

Risk:
- high privilege in local environment

Mitigation guidance:
- keep runner internal-only
- require token
- restrict who can trigger pipeline endpoints (`ADMIN`, `DATA_MLOPS_ENGINEER`)

## Local credentials warning
- seeded admin account and default secrets are for local PoC only
- rotate secrets and tighten network exposure for any shared/non-local environment
