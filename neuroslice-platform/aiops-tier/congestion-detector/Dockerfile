FROM python:3.11-slim
WORKDIR /app

COPY ingestion-tier/shared/ shared/
COPY aiops-tier/shared/ shared/

COPY aiops-tier/congestion-detector/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY aiops-tier/congestion-detector/ .

CMD ["python", "main.py"]
