FROM python:3.11-slim

WORKDIR /app

COPY ingestion-tier/shared/ shared/

COPY ingestion-tier/telemetry-exporter/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ingestion-tier/telemetry-exporter/main.py .

CMD ["python", "-u", "main.py"]
