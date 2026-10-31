"""Configuración centralizada. Todo sale de variables de entorno (nunca del bundle de React)."""
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Aurora VIII"
    environment: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"

    # Base de datos (Supabase: usar la cadena "Session pooler" o conexión directa)
    database_url: str = "postgresql+psycopg://aurora:aurora@localhost:5432/aurora"

    # CORS: orígenes del frontend separados por coma (p. ej. https://aurora-viii.vercel.app)
    cors_origins: str = "http://localhost:5173"
    # Expresión regular opcional para previews de Vercel (p. ej. https://aurora-viii-.*\.vercel\.app)
    cors_origin_regex: str | None = None

    # Autenticación
    #  - supabase: valida JWT emitidos por Supabase Auth (JWKS o secreto HS256 legado)
    #  - local:    emite tokens propios (solo dev/test/demo; desactivado en prod salvo ALLOW_LOCAL_AUTH_IN_PROD)
    auth_mode: Literal["supabase", "local"] = "local"
    supabase_url: str | None = None
    supabase_jwt_secret: str | None = None  # opcional, solo proyectos con secreto legado
    supabase_jwt_audience: str = "authenticated"
    # Solo servidor (Storage). Preferida: la nueva secret key (sb_secret_...). La service_role legada
    # sigue funcionando mientras Supabase la mantenga (anunció su retiro para fines de 2026).
    supabase_secret_key: str | None = None
    supabase_service_role_key: str | None = None
    local_jwt_secret: str = "dev-only-change-me-dev-only-change-me"
    allow_local_auth_in_prod: bool = False
    # Correos que se convierten en administradores al primer ingreso (coma)
    bootstrap_admin_emails: str = ""

    # Almacenamiento de objetos
    storage_backend: Literal["local", "supabase"] = "local"
    storage_local_dir: str = "./.storage"
    storage_bucket: str = "aurora-viii"

    # Worker
    run_worker_in_process: bool = False  # True = un solo servicio en Render (plan gratuito)
    worker_poll_seconds: float = 1.5
    worker_heartbeat_seconds: float = 5.0
    worker_stale_after_seconds: float = 120.0

    # Límites de recursos (valores por defecto; editables en system_settings)
    max_epochs: int = 200
    max_batch_size: int = 512
    max_layers: int = 12
    max_units_per_layer: int = 512
    max_parameters: int = 2_000_000
    max_upload_mb: int = 10
    max_concurrent_jobs_per_user: int = 2
    max_queued_jobs_per_project: int = 10
    job_timeout_seconds: int = 900
    rate_limit_per_minute: int = 240

    @field_validator("database_url")
    @classmethod
    def normalize_db_url(cls, v: str) -> str:
        # Render/Supabase entregan postgres:// o postgresql:// → forzamos el driver psycopg 3
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    @property
    def supabase_server_key(self) -> str | None:
        return self.supabase_secret_key or self.supabase_service_role_key

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    @property
    def admin_emails(self) -> set[str]:
        return {e.strip().lower() for e in self.bootstrap_admin_emails.split(",") if e.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
