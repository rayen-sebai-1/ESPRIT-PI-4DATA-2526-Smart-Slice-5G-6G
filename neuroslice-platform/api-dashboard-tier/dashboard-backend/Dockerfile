FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY api-dashboard-tier/dashboard-backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

COPY api-dashboard-tier/dashboard-backend/ /app/
RUN chmod +x /app/scripts/start.sh

CMD ["./scripts/start.sh"]
