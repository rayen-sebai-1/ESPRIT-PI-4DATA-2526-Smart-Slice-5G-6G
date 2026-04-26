# React Dashboard

`react-dashboard` is the protected React frontend for the NeuroSlice operations dashboard.

## Stack

- React 18
- Vite 5
- TypeScript
- Tailwind CSS
- TanStack Query
- Axios
- Recharts

## Runtime Model

- default UI URL: `http://localhost:5173`
- all browser API traffic goes through Kong
- access tokens are kept in memory
- refresh uses the HttpOnly refresh cookie issued by `auth-service`
- Vite proxies `/api/*` to `http://localhost:8008` by default

## Routes

- `/login`
- `/dashboard/national`
- `/dashboard/region`
- `/dashboard/region/:regionId`
- `/sessions`
- `/predictions`
- `/admin/users`
- `*` -> not found page

Current route guards in the router:

- all authenticated users can access the dashboard shell
- `/sessions`: `ADMIN`, `NETWORK_OPERATOR`
- `/predictions`: `ADMIN`, `NETWORK_OPERATOR`, `DATA_MLOPS_ENGINEER`
- `/admin/users`: `ADMIN`

`NETWORK_MANAGER` currently has dashboard access only in the shipped UI, even though the backend prediction API accepts that role.

## Local Development

```bash
cd neuroslice-platform/api-dashboard-tier/react-dashboard
npm ci
npm run dev
```

Build and preview:

```bash
npm run build
npm run preview
```

## Environment Variables

- `VITE_DEV_PROXY_TARGET` default `http://localhost:8008`
- `VITE_AUTH_API_URL` default `/api/auth`
- `VITE_DASHBOARD_API_URL` default `/api/dashboard`
- `VITE_SESSION_API_URL` optional override
- `VITE_PREDICTION_API_URL` optional override

## Docker Runtime

The Docker image:

- uses `node:20-alpine`
- runs `npm ci`
- starts `npm run dev -- --host 0.0.0.0 --port 5173`

This is a development-oriented container, not a production static build image.

## Verification

```bash
npm run build
curl http://localhost:5173
```

When the platform is running, browser network calls should target `/api/auth/*` and `/api/dashboard/*`; Vite forwards them to Kong at `http://localhost:8008`.
