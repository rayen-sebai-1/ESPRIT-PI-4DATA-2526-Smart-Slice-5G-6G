FROM python:3.11-slim

WORKDIR /app

# Copy shared models
COPY shared/ /shared/
ENV PYTHONPATH=/

COPY kafka-influx-consumer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY kafka-influx-consumer/main.py .

CMD ["python", "-u", "main.py"]
