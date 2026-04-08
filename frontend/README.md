# NeuroSlice Tunisia Frontend

Frontend React V1 du backend MVP existant NeuroSlice Tunisia.

## Stack

- React
- TypeScript
- Vite
- TailwindCSS
- React Router
- TanStack Query
- Axios
- Recharts

## Pages V1

- Login
- Dashboard National
- Dashboard Regional
- Sessions Monitor
- Predictions Center

## Prerequis

Les services backend doivent etre demarres localement :

- Auth : `http://localhost:8001`
- Sessions : `http://localhost:8002`
- Predictions : `http://localhost:8003`
- Dashboard : `http://localhost:8004`

## Demarrage local

```bash
npm install
npm run dev
```

Frontend local :

- `http://localhost:5173`

## Important

Le backend MVP n'expose pas encore CORS pour une application frontend separee.
Pour garder une integration propre sans modifier l'architecture backend, cette V1 utilise le proxy Vite :

- `/api/auth` -> `http://localhost:8001`
- `/api/session` -> `http://localhost:8002`
- `/api/prediction` -> `http://localhost:8003`
- `/api/dashboard` -> `http://localhost:8004`

## Comptes de demo

- `admin@neuroslice.tn / admin123`
- `operator@neuroslice.tn / operator123`
- `manager@neuroslice.tn / manager123`

## Notes UX

- la page `Predictions Center` appelle bien `/predictions`
- la vue `Models` appelle `/models`
- si `/models` retourne une erreur backend, le frontend affiche un fallback propre sans casser la page
- la vue `Sessions Monitor` consomme `/sessions` et le detail utilise `/sessions/{id}`
