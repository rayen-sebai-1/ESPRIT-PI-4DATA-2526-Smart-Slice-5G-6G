FROM python:3.11-slim
WORKDIR /app

COPY ingestion-tier/shared/ shared/

COPY simulation-tier/fault-engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY simulation-tier/fault-engine/ .

CMD ["python", "main.py"]
