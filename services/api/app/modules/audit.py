import uuid

from sqlalchemy.orm import Session

from app.models import AuditEvent


def record(db: Session, actor_id: uuid.UUID | None, project_id: uuid.UUID | None, action: str,
           metadata: dict | None = None) -> None:
    """Registra una acción relevante. El commit lo hace quien llama (misma transacción que la acción)."""
    db.add(AuditEvent(actor_id=actor_id, project_id=project_id, action=action, metadata_json=metadata or {}))
