FROM python:3.11-slim
WORKDIR /app

COPY shared/ shared/

COPY adapter-ves/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY adapter-ves/ .

CMD ["python", "main.py"]
