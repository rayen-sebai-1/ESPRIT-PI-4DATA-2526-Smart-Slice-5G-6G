FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7005

WORKDIR /app

COPY root-cause/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared ./shared
COPY root-cause .

EXPOSE 7005

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7005}"]
