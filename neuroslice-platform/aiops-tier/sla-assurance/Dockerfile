FROM python:3.11-slim
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY ingestion-tier/shared/ shared/
COPY aiops-tier/shared/ shared/

COPY aiops-tier/sla-assurance/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY aiops-tier/sla-assurance/ .

CMD ["python", "main.py"]
