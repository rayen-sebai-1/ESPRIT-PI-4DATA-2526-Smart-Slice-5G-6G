FROM python:3.11-slim
WORKDIR /app

# Copy shared library into the app directory so `import shared` works directly
COPY shared/ shared/

COPY simulator-core/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY simulator-core/ .

CMD ["python", "main.py"]
