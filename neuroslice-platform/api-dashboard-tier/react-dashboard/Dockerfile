# ── Stage 1: Build ────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY api-dashboard-tier/react-dashboard/package*.json ./
RUN npm ci

COPY api-dashboard-tier/react-dashboard/ ./

# VITE_* vars are baked in at build time. Kong gateway is the API target in prod.
ARG VITE_AUTH_API_URL=/api/auth
ARG VITE_DASHBOARD_API_URL=/api/dashboard
ENV VITE_AUTH_API_URL=$VITE_AUTH_API_URL
ENV VITE_DASHBOARD_API_URL=$VITE_DASHBOARD_API_URL

RUN npm run build

# ── Stage 2: Serve ────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runner

# Remove default nginx config and replace with our own
RUN rm /etc/nginx/conf.d/default.conf

COPY api-dashboard-tier/react-dashboard/nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 5173

CMD ["nginx", "-g", "daemon off;"]
