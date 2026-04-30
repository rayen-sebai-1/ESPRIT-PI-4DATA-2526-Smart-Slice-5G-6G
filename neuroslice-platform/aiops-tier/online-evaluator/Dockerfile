FROM python:3.11-slim
WORKDIR /app

COPY aiops-tier/online-evaluator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY aiops-tier/online-evaluator/ .

CMD ["python", "main.py"]
