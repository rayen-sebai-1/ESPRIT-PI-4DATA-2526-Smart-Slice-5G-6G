FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVICE_PORT=7010

WORKDIR /app

COPY control-tier/alert-management/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY control-tier/alert-management/app ./app

EXPOSE 7010

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${SERVICE_PORT:-7010}"]
