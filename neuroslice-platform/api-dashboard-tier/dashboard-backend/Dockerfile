FROM python:3.11-slim

ARG SERVICE_MODULE=api_service.main:app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    SERVICE_MODULE=${SERVICE_MODULE}

WORKDIR /app

COPY api-dashboard-tier/dashboard-backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

COPY api-dashboard-tier/dashboard-backend/ /app/

CMD ["sh", "-c", "uvicorn ${SERVICE_MODULE} --host 0.0.0.0 --port 8000"]
