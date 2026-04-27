FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVICE_PORT=7011

WORKDIR /app

COPY control-tier/policy-control/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY control-tier/policy-control/app ./app

EXPOSE 7011

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${SERVICE_PORT:-7011}"]
