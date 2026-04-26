FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7006

WORKDIR /app

COPY copilot-agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared ./shared
COPY copilot-agent .

EXPOSE 7006

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7006}"]
