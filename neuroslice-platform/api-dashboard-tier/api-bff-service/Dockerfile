FROM python:3.11-slim
WORKDIR /app

COPY ingestion-tier/shared/ shared/

COPY api-dashboard-tier/api-bff-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api-dashboard-tier/api-bff-service/ .

CMD ["python", "main.py"]
