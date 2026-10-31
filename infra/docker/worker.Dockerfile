# Aurora VIII · Worker de entrenamiento TensorFlow/Keras (necesita ~1 GB de RAM; recomendado 2 GB).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/api:/app/worker MIGRATIONS_DIR=/app/migrations TF_CPP_MIN_LOG_LEVEL=2

WORKDIR /app
COPY services/api/requirements.txt /tmp/api-req.txt
COPY workers/training/requirements.txt /tmp/worker-req.txt
RUN pip install -r /tmp/api-req.txt -r /tmp/worker-req.txt

COPY services/api/app /app/api/app
COPY workers/training/aurora_worker /app/worker/aurora_worker
COPY infra/migrations /app/migrations

RUN useradd --create-home --uid 10001 aurora && mkdir -p /app/.storage && chown -R aurora /app
USER aurora
WORKDIR /app/worker
CMD ["python", "-m", "aurora_worker"]
