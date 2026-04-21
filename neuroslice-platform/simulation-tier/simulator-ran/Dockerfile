FROM python:3.11-slim
WORKDIR /app

COPY ingestion-tier/shared/ shared/

COPY simulation-tier/simulator-ran/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY simulation-tier/simulator-ran/ .

CMD ["python", "main.py"]
