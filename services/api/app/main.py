"""Aurora VIII · API (FastAPI). Arranque: migraciones, datasets demo y, opcionalmente, worker en proceso."""
import logging
import threading
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1 import admin, architectures, auth, catalog, datasets, models_registry, projects, reports, training
from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.core.logging import setup_logging
from app.core.migrate import run_migrations
from app.core.ratelimit import RateLimiter

settings = get_settings()
setup_logging(settings.log_level)
log = logging.getLogger("aurora.api")
limiter = RateLimiter(settings.rate_limit_per_minute)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auth_mode == "local" and settings.environment == "prod" and not settings.allow_local_auth_in_prod:
        log.warning("AUTH_MODE=local en prod: el acceso local está desactivado. Configura AUTH_MODE=supabase.")
    applied = run_migrations()
    if applied:
        log.info("Migraciones aplicadas: %s", applied)
    with SessionLocal() as db:
        datasets.seed_builtin_datasets(db)
    if settings.storage_backend == "supabase":
        from app.modules.storage import get_storage
        try:
            get_storage().ensure_bucket()
        except Exception as exc:  # noqa: BLE001 — la API arranca igual y lo informa
            log.error("Supabase Storage no está listo: %s", exc)
    stop = threading.Event()
    if settings.run_worker_in_process:
        from app.worker_bridge import start_embedded_worker
        start_embedded_worker(stop)
    yield
    stop.set()


app = FastAPI(title="Aurora VIII API", version="1.0.0", lifespan=lifespan,
              description="Plataforma enterprise de redes neuronales artificiales (Semana 11).",
              docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)

app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_origin_regex=settings.cors_origin_regex,
                   allow_credentials=False, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                   allow_headers=["Authorization", "Content-Type", "Last-Event-ID"],
                   expose_headers=["Content-Disposition", "X-Checksum-SHA256", "X-Request-ID"])


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    client = request.headers.get("authorization", "")[-24:] or (request.client.host if request.client else "anon")
    if request.url.path.startswith("/api/v1") and not request.url.path.endswith("/events") and not limiter.allow(client):
        return JSONResponse({"detail": "Demasiadas solicitudes. Intenta en un minuto."}, status_code=429)
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("Error no controlado", extra={"request_id": rid, "path": request.url.path})
        return JSONResponse({"detail": "Error interno. Referencia: " + rid}, status_code=500,
                            headers={"X-Request-ID": rid})
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if not request.url.path.endswith("/events"):
        log.info("%s %s", request.method, request.url.path,
                 extra={"request_id": rid, "path": request.url.path, "status": response.status_code,
                        "ms": round((time.perf_counter() - t0) * 1000, 1)})
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    issues = [{"path": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse({"detail": {"message": "Datos inválidos", "issues": issues}}, status_code=422)


for r in (auth.router, catalog.router, projects.router, datasets.router, architectures.router, training.router,
          models_registry.router, reports.router, admin.router):
    app.include_router(r, prefix="/api/v1")


@app.get("/healthz", include_in_schema=False)
def healthz():
    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    return {"status": "ok", "service": "aurora-viii-api"}


@app.get("/", include_in_schema=False)
def root():
    return {"service": "Aurora VIII API", "docs": "/api/docs"}
