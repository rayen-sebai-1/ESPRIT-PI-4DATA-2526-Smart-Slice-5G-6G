FROM python:3.11-slim
WORKDIR /app

COPY ingestion-tier/shared/ shared/

COPY ingestion-tier/normalizer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ingestion-tier/normalizer/ .

CMD ["python", "main.py"]
