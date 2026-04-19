FROM python:3.11-slim
WORKDIR /app

COPY shared/ shared/

COPY normalizer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY normalizer/ .

CMD ["python", "main.py"]
