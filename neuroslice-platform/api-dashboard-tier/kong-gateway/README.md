# Kong Gateway

Last verified: 2026-04-29.

`kong-gateway` is the browser-facing API gateway for the protected NeuroSlice dashboard stack.

## Current Role

- exposes the only public protected API endpoint at `http://localhost:8008`
- routes auth requests to `auth-service`
- routes dashboard requests to `dashboard-backend`
- keeps the public telemetry BFF separate from the protected dashboard flow

Kong is currently doing routing, CORS, and rate limiting only. Authentication and role checks are still enforced by `auth-service` and `dashboard-backend`.

## Configuration Sources

- Docker build entry: `kong-gateway/Dockerfile`
- declarative config: `kong-gateway/kong.yml`

## Route Mapping

`kong.yml` currently maps:

- `POST /api/auth/login` -> `auth-service:8001/auth/login`
- other `/api/auth/*` routes -> `auth-service:8001/auth/*`
- `/api/auth/users*` -> `auth-service:8001/users*`
- `/api/dashboard/sessions*` -> `dashboard-backend:8002/sessions*`
- `/api/dashboard/predictions*` -> `dashboard-backend:8002/predictions*`
- `/api/dashboard/models` -> `dashboard-backend:8002/models`
- `/api/dashboard/agentic*` -> `dashboard-backend:8002/agentic*` (JWT-validated agentic proxy)
- `/api/dashboard/controls*` -> `dashboard-backend:8002/controls*`
- other `/api/dashboard/*` routes -> `dashboard-backend:8002/dashboard/*`

Agentic routes (`/api/dashboard/agentic/*`) go through `dashboard-backend`, which validates the Bearer token and enforces role checks before proxying to internal agent services. The old direct agentic routes (`/api/agentic/*`) have been removed.

## Active Plugins

Global plugin:

- CORS with credentials enabled for `http://localhost:5173` and `http://127.0.0.1:5173`

Route-level plugins:

- login route: rate limit `5` requests per minute and `100` per hour
- protected dashboard routes: rate limit `120` requests per minute and `5000` per hour
- all `/api/dashboard/*` routes: `request-transformer` injects `X-Kong-Authenticated: true` header so downstream services can verify the request passed through the gateway

## Validation

```bash
cd neuroslice-platform/infrastructure
docker compose exec kong-gateway kong health
curl -i http://localhost:8008/api/auth/me
```

`kong health` validates the gateway process. The auth probe validates that gateway routing is active and should return an authentication error unless a valid access token is provided.

## Current Scope

- there is no second gateway configuration in this repository
- health routes for `auth-service` and `dashboard-backend` are internal and are not exposed through Kong
- JWT validation is not implemented in Kong; protected services (`auth-service`, `dashboard-backend`) validate tokens themselves
- the `request-transformer` plugin marks gateway-routed requests with `X-Kong-Authenticated: true` but does not perform token verification itself
