# React Dashboard

Canonical frontend for the protected NeuroSlice dashboard stack.

## Role

- Contains the full React + Vite application source (`src/`, `package.json`, `vite.config.ts`, Tailwind config, and assets).
- Is the only browser-facing dashboard UI project in `api-dashboard-tier/`.
- Keeps the access token in memory only and refreshes sessions through an `HttpOnly` cookie flow.
- Sends all dashboard traffic through Kong only:
  - `/api/auth/*`
  - `/api/dashboard/*`

## Runtime

- Docker build entry: `react-dashboard/Dockerfile`
- Local dev/build files live directly in this folder
- Default UI URL: `http://localhost:5173`

## Ownership

- `react-dashboard/` is the only authoritative frontend runtime component.
- There is no secondary `dashboard-frontend/` folder anymore.
