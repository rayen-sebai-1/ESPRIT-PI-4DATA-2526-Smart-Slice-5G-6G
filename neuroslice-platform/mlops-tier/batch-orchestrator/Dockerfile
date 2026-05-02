FROM python:3.10-slim

# Pass cpu to use lightweight CPU wheels in CI; defaults to CUDA 12.6 for prod.
ARG PYTORCH_INDEX=cu126

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libgomp1 \
    make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
# Install PyTorch via the index selected by the build arg, then install the
# remaining requirements (stripping the torch/CUDA lines to avoid conflicts).
RUN pip install --no-cache-dir torch torchvision \
        --index-url "https://download.pytorch.org/whl/${PYTORCH_INDEX}" && \
    grep -vE '^(torch|torchvision|--extra-index-url)' requirements.txt \
        | pip install --no-cache-dir -r /dev/stdin

# Copy application code
COPY Makefile MLproject ./
COPY src/ ./src/
COPY data/ ./data/
COPY models/ ./models/
COPY reports/ ./reports/
COPY tests/ ./tests/

ENV API_PORT=8010

EXPOSE 8010

CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port ${API_PORT:-8010}"]
