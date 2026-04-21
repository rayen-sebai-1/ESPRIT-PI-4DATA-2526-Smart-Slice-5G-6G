FROM node:20-alpine

WORKDIR /app

COPY api-dashboard-tier/dashboard-frontend/package*.json ./
RUN npm ci

COPY api-dashboard-tier/dashboard-frontend/ ./

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
