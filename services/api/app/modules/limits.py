"""Límites de recursos efectivos = valores de entorno sobrescritos por system_settings (Administración)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import SystemSetting

KEYS = ["max_epochs", "max_batch_size", "max_layers", "max_units_per_layer", "max_parameters", "max_upload_mb",
        "max_concurrent_jobs_per_user", "max_queued_jobs_per_project", "job_timeout_seconds", "event_retention_days"]
BOUNDS = {"max_epochs": (1, 5000), "max_batch_size": (1, 4096), "max_layers": (1, 64),
          "max_units_per_layer": (1, 4096), "max_parameters": (100, 50_000_000), "max_upload_mb": (1, 200),
          "max_concurrent_jobs_per_user": (1, 50), "max_queued_jobs_per_project": (1, 500),
          "job_timeout_seconds": (30, 86_400), "event_retention_days": (1, 3650)}


def effective_limits(db: Session) -> dict:
    s = get_settings()
    out = {k: getattr(s, k) for k in KEYS if hasattr(s, k)}
    out.setdefault("event_retention_days", 30)
    for row in db.scalars(select(SystemSetting).where(SystemSetting.key.in_(KEYS))):
        out[row.key] = row.value_json
    return out
