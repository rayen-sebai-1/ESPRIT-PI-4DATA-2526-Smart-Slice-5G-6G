# Kong Gateway

Canonical API gateway entry for the Scenario B dashboard stack.

## Role

- Publishes the only browser-facing dashboard API surface.
- Routes auth traffic to `auth-service`.
- Routes dashboard domain traffic to `dashboard-backend`.
- Keeps the platform BFF (`api-bff-service`) separate from the protected dashboard flow.

## Runtime

- Docker build entry: `kong-gateway/Dockerfile`
- Declarative config: `kong-gateway/kong.yml`
- Default public URL: `http://localhost:8008`

## Public Routes

- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET|POST|PATCH|DELETE /api/auth/users`
- `GET /api/dashboard/national`
- `GET /api/dashboard/region/{regionId}`
- `GET /api/dashboard/sessions`
- `GET /api/dashboard/sessions/{sessionId}`
- `GET /api/dashboard/predictions`
- `GET /api/dashboard/predictions/{sessionId}`
- `POST /api/dashboard/predictions/run/{sessionId}`
- `POST /api/dashboard/predictions/run-batch`
- `GET /api/dashboard/models`
- `GET|PUT /api/dashboard/preferences/me`
- `GET|POST|DELETE /api/dashboard/bookmarks`
- `POST /api/dashboard/alerts/{alertKey}/acknowledge`

## Ownership

- `kong-gateway/` is the only authoritative dashboard gateway component.
- There is no secondary `kong/` folder anymore.
