"""Ejecuta las migraciones SQL de infra/migrations en orden. Uso: python -m app.core.migrate"""
import logging
import os
from pathlib import Path

from sqlalchemy import text

from app.core.db import engine

log = logging.getLogger("aurora.migrate")


def migrations_dir() -> Path:
    env = os.getenv("MIGRATIONS_DIR")
    candidates = [Path(env)] if env else []
    here = Path(__file__).resolve()
    candidates += [here.parents[4] / "infra" / "migrations", Path("/app/migrations"), Path.cwd() / "migrations"]
    for c in candidates:
        if c.is_dir():
            return c
    raise RuntimeError("No se encontró la carpeta de migraciones (define MIGRATIONS_DIR)")


def run_migrations() -> list[str]:
    applied: list[str] = []
    files = sorted(migrations_dir().glob("*.sql"))
    with engine.begin() as conn:
        # Bloqueo consultivo: evita que API y worker migren a la vez
        conn.execute(text("SELECT pg_advisory_xact_lock(814201)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"))
        done = {r[0] for r in conn.execute(text("SELECT version FROM schema_migrations"))}
        for f in files:
            version = f.stem
            if version in done:
                continue
            log.info("Aplicando migración %s", version)
            # Cursor del driver sin parámetros: el SQL puede contener % (p. ej. format('%I'))
            conn.connection.driver_connection.execute(f.read_text(encoding="utf-8"))
            conn.execute(text("INSERT INTO schema_migrations(version) VALUES (:v) ON CONFLICT DO NOTHING"), {"v": version})
            applied.append(version)
    return applied


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Aplicadas:", run_migrations() or "ninguna (al día)")
