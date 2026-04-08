FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY index.html ./
COPY postcss.config.js ./
COPY tailwind.config.ts ./
COPY tsconfig.json ./
COPY tsconfig.app.json ./
COPY tsconfig.node.json ./
COPY vite.config.ts ./
COPY src ./src
COPY public ./public

ARG VITE_AUTH_API_URL=/api/auth
ARG VITE_SESSION_API_URL=/api/session
ARG VITE_PREDICTION_API_URL=/api/prediction
ARG VITE_DASHBOARD_API_URL=/api/dashboard

ENV VITE_AUTH_API_URL=${VITE_AUTH_API_URL}
ENV VITE_SESSION_API_URL=${VITE_SESSION_API_URL}
ENV VITE_PREDICTION_API_URL=${VITE_PREDICTION_API_URL}
ENV VITE_DASHBOARD_API_URL=${VITE_DASHBOARD_API_URL}

RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
