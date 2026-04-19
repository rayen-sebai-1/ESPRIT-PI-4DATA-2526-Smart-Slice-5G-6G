FROM python:3.11-slim
WORKDIR /app

COPY shared/ shared/

COPY fault-engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fault-engine/ .

CMD ["python", "main.py"]
