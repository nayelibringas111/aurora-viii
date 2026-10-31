# Aurora VIII · API (FastAPI). Imagen liviana (~100 MB de RAM en ejecución) SIN TensorFlow.
# Para el modo "todo en uno" (API + worker embebido) construye con: --build-arg WITH_TF=true
FROM python:3.12-slim

ARG WITH_TF=false
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/api:/app/worker MIGRATIONS_DIR=/app/migrations TF_CPP_MIN_LOG_LEVEL=2

WORKDIR /app
COPY services/api/requirements.txt /tmp/api-req.txt
COPY workers/training/requirements.txt /tmp/worker-req.txt
RUN pip install -r /tmp/api-req.txt && \
    if [ "$WITH_TF" = "true" ]; then pip install -r /tmp/worker-req.txt; fi

COPY services/api/app /app/api/app
COPY workers/training/aurora_worker /app/worker/aurora_worker
COPY infra/migrations /app/migrations

RUN useradd --create-home --uid 10001 aurora && mkdir -p /app/.storage && chown -R aurora /app
USER aurora
WORKDIR /app/api
EXPOSE 8000
# Render inyecta $PORT; en local se usa 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
