FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

ARG SERVICE_MODULE
ENV SERVICE_MODULE=${SERVICE_MODULE}

EXPOSE 8000

CMD sh -c "uvicorn ${SERVICE_MODULE} --host 0.0.0.0 --port ${PORT:-8000}"
