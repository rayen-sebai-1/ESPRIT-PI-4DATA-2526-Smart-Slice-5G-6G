FROM python:3.11-slim
WORKDIR /app

COPY ingestion-tier/shared/ shared/

COPY ingestion-tier/logstash-aiops-ingest/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ingestion-tier/logstash-aiops-ingest/ .

CMD ["python", "main.py"]
