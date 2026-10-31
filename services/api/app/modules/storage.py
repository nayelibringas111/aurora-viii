"""Almacenamiento de objetos para datasets y modelos (los archivos grandes no viven en filas de PostgreSQL).

- local:    carpeta en disco (desarrollo). En Render el disco es efímero: usar supabase en producción.
- supabase: Supabase Storage vía REST con la service_role key (solo servidor, bucket privado).
"""
from pathlib import Path

import httpx

from app.core.config import get_settings

settings = get_settings()


class StorageError(RuntimeError):
    pass


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise StorageError("Clave de almacenamiento inválida")
        return p

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get(self, key: str) -> bytes:
        p = self._path(key)
        if not p.exists():
            raise StorageError("Objeto no encontrado")
        return p.read_bytes()

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()


class SupabaseStorage:
    def __init__(self, url: str, service_key: str, bucket: str):
        self.base = f"{url.rstrip('/')}/storage/v1"
        self.bucket = bucket
        # Las nuevas secret keys (sb_secret_...) van SOLO en la cabecera apikey; la service_role legada es un JWT
        self.headers = {"apikey": service_key}
        if not service_key.startswith("sb_"):
            self.headers["Authorization"] = f"Bearer {service_key}"

    def ensure_bucket(self) -> None:
        """Crea el bucket privado si no existe (idempotente)."""
        r = httpx.get(f"{self.base}/bucket/{self.bucket}", headers=self.headers, timeout=20)
        if r.status_code == 200:
            return
        r = httpx.post(f"{self.base}/bucket", headers=self.headers, timeout=20,
                       json={"id": self.bucket, "name": self.bucket, "public": False})
        if r.status_code >= 300 and "already exists" not in r.text.lower():
            raise StorageError(f"No se pudo crear el bucket «{self.bucket}» ({r.status_code})")

    def _url(self, key: str) -> str:
        return f"{self.base}/object/{self.bucket}/{key}"

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        r = httpx.post(self._url(key), content=data, timeout=120,
                       headers={**self.headers, "Content-Type": content_type, "x-upsert": "true"})
        if r.status_code >= 300:
            raise StorageError(f"Supabase Storage rechazó la subida ({r.status_code})")

    def get(self, key: str) -> bytes:
        r = httpx.get(self._url(key), headers=self.headers, timeout=120)
        if r.status_code >= 300:
            raise StorageError(f"Supabase Storage no devolvió el objeto ({r.status_code})")
        return r.content

    def delete(self, key: str) -> None:
        httpx.request("DELETE", f"{self.base}/object/{self.bucket}", headers=self.headers,
                      json={"prefixes": [key]}, timeout=30)


_storage = None


def get_storage():
    global _storage
    if _storage is None:
        if settings.storage_backend == "supabase":
            if not (settings.supabase_url and settings.supabase_server_key):
                raise StorageError("STORAGE_BACKEND=supabase requiere SUPABASE_URL y SUPABASE_SECRET_KEY")
            _storage = SupabaseStorage(settings.supabase_url, settings.supabase_server_key, settings.storage_bucket)
        else:
            _storage = LocalStorage(settings.storage_local_dir)
    return _storage
