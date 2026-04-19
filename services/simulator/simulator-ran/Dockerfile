FROM python:3.11-slim
WORKDIR /app

COPY shared/ shared/

COPY simulator-ran/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY simulator-ran/ .

CMD ["python", "main.py"]
