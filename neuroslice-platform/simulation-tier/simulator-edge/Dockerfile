FROM python:3.11-slim
WORKDIR /app

COPY ingestion-tier/shared/ shared/

COPY simulation-tier/simulator-edge/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY simulation-tier/simulator-edge/ .

CMD ["python", "main.py"]
