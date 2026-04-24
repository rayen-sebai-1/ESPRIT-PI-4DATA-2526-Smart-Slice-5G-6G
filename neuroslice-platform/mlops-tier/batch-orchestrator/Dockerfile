FROM python:3.10-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libgomp1 \
    make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY data/ ./data/
COPY models/ ./models/
COPY mlruns/ ./mlruns/

ENV API_PORT=8010

EXPOSE 8010

CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port ${API_PORT:-8010}"]
