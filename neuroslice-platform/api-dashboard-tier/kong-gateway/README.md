# Kong Gateway

`kong-gateway` is the browser-facing API gateway for the protected NeuroSlice dashboard stack.

## Current Role

- exposes the only public protected API endpoint at `http://localhost:8008`
- routes auth requests to `auth-service`
- routes dashboard requests to `dashboard-backend`
- keeps the public telemetry BFF separate from the protected dashboard flow

## Configuration Sources

- Docker build entry: `kong-gateway/Dockerfile`
- declarative config: `kong-gateway/kong.yml`

## Route Mapping

`kong.yml` currently maps:

- `POST /api/auth/login` -> `auth-service:8001/auth/login`
- `/api/auth/*` -> `auth-service:8001/auth/*`
- `/api/auth/users*` -> `auth-service:8001/users*`
- `/api/dashboard/sessions*` -> `dashboard-backend:8002/sessions*`
- `/api/dashboard/predictions*` -> `dashboard-backend:8002/predictions*`
- `/api/dashboard/models` -> `dashboard-backend:8002/models`
- other `/api/dashboard/*` routes -> `dashboard-backend:8002/dashboard/*`

## Active Plugins

Global plugin:

- CORS with credentials enabled for `http://localhost:5173` and `http://127.0.0.1:5173`

Route-level rate limits:

- login route: `5` requests per minute and `100` per hour
- protected dashboard routes: `120` requests per minute and `5000` per hour

## Validation

```bash
cd neuroslice-platform/infrastructure
docker compose exec kong-gateway kong health
```

## Current Scope

- There is no secondary gateway folder in this repository.
- Health routes for `auth-service` and `dashboard-backend` are internal and are not exposed through Kong.
