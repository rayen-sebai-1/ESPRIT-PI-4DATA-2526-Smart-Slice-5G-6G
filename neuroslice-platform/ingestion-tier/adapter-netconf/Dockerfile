FROM python:3.11-slim
WORKDIR /app

COPY ingestion-tier/shared/ shared/

COPY ingestion-tier/adapter-netconf/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ingestion-tier/adapter-netconf/ .

CMD ["python", "main.py"]
