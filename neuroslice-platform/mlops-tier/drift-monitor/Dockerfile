FROM python:3.12-slim

WORKDIR /app

COPY mlops-tier/drift-monitor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mlops-tier/drift-monitor/main.py .

EXPOSE 8030

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8030"]
