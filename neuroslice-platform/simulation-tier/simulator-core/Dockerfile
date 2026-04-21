FROM python:3.11-slim
WORKDIR /app

# Copy shared library into the app directory so `import shared` works directly
COPY ingestion-tier/shared/ shared/

COPY simulation-tier/simulator-core/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY simulation-tier/simulator-core/ .

CMD ["python", "main.py"]
