"""Fixtures de prueba. Requiere un PostgreSQL desechable:

    TEST_DATABASE_URL=postgresql://aurora:aurora@localhost:5432/aurora_test pytest

La base se recrea al inicio de la sesión de pruebas.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql://aurora:aurora@localhost:5432/aurora_test")
os.environ.update({
    "DATABASE_URL": TEST_DB, "ENVIRONMENT": "test", "AUTH_MODE": "local", "LOG_LEVEL": "WARNING",
    "STORAGE_BACKEND": "local", "STORAGE_LOCAL_DIR": tempfile.mkdtemp(prefix="aurora-test-"),
    "RUN_WORKER_IN_PROCESS": "false", "RATE_LIMIT_PER_MINUTE": "100000",
    "MIGRATIONS_DIR": str(ROOT / "infra" / "migrations"),
})
sys.path[:0] = [str(ROOT / "services" / "api"), str(ROOT / "workers" / "training")]


def _recreate_database():
    import psycopg
    base, name = TEST_DB.rsplit("/", 1)
    with psycopg.connect(f"{base}/postgres", autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        c.execute(f'CREATE DATABASE "{name}"')


_recreate_database()

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def _login(client, email, name="Usuario"):
    tok = client.post("/api/v1/auth/local-login", json={"email": email, "display_name": name}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/v1/me", headers=h).status_code == 200  # el usuario se crea en su primer acceso
    return h


@pytest.fixture(scope="session")
def admin(client):
    return _login(client, "admin@aurora-lab.dev", "Admin")  # primer usuario fuera de prod = administrador


@pytest.fixture
def login(client, admin):
    return lambda email, name="Usuario": _login(client, email, name)


@pytest.fixture
def project(client, admin):
    return client.post("/api/v1/projects", headers=admin, json={"name": "Proyecto de prueba"}).json()


@pytest.fixture
def ff_arch(client, admin, project):
    from app.modules.catalog import FAMILIES
    tpl = next(f for f in FAMILIES if f["id"] == "feedforward")["template"]
    return client.post(f"/api/v1/projects/{project['id']}/architectures", headers=admin,
                       json={"name": "ff", "family": "feedforward", "config": tpl}).json()


@pytest.fixture
def datasets(client, admin, project):
    return {d["name"]: d for d in client.get(f"/api/v1/projects/{project['id']}/datasets", headers=admin).json()}
