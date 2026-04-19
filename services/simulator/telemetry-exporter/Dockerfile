FROM python:3.11-slim
WORKDIR /app

COPY shared/ shared/

COPY telemetry-exporter/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY telemetry-exporter/ .

CMD ["python", "main.py"]
