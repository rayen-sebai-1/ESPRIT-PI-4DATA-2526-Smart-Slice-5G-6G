FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY api-dashboard-tier/auth-service/requirements.txt ./requirements.txt

RUN apt-get update && apt-get install -y --no-install-recommends bash dos2unix && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY api-dashboard-tier/auth-service/ ./

RUN dos2unix ./scripts/start.sh ./scripts/*.py && \
    chmod +x ./scripts/start.sh

CMD ["bash", "./scripts/start.sh"]