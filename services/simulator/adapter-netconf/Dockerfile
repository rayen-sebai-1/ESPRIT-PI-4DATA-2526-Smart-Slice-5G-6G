FROM python:3.11-slim
WORKDIR /app

COPY shared/ shared/

COPY adapter-netconf/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY adapter-netconf/ .

CMD ["python", "main.py"]
