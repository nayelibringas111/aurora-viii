import uuid

from fastapi import HTTPException, status


def parse_uuid(value: str, what: str = "recurso") -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{what.capitalize()} no encontrado")


def iso(dt) -> str | None:
    return dt.isoformat() if dt else None
