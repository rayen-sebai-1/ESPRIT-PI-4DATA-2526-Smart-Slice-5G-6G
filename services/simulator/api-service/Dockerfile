FROM python:3.11-slim
WORKDIR /app

COPY shared/ shared/

COPY api-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api-service/ .

CMD ["python", "main.py"]
