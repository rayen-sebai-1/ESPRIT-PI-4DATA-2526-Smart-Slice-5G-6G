FROM python:3.11-slim

WORKDIR /app

# System deps for numpy / torch compilation if needed from source
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY aiops-tier/drift-monitor/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY aiops-tier/drift-monitor/app /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 7012

CMD ["python", "main.py"]
