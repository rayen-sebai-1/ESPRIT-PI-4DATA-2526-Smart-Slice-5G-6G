FROM python:3.11-slim

WORKDIR /app

# Default to CPU wheels for broad compatibility; override with cu126 if needed.
ARG PYTORCH_INDEX=cpu

# System deps for numpy / torch compilation if needed from source
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY aiops-tier/drift-monitor/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir torch \
        --index-url "https://download.pytorch.org/whl/${PYTORCH_INDEX}" && \
    grep -vE '^(torch|--extra-index-url)' /tmp/requirements.txt \
        | pip install --no-cache-dir -r /dev/stdin

COPY aiops-tier/drift-monitor/app /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 7012

CMD ["python", "main.py"]
