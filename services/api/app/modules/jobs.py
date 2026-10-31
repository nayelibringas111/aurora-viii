"""Máquina de estados de los entrenamientos y emisión de eventos.

QUEUED → PREPARING → RUNNING → COMPLETED | FAILED | CANCELLED
QUEUED → CANCELLED (cancelación antes de empezar)
PREPARING/RUNNING → QUEUED (reintento automático si el worker muere; limitado por max_attempts)
"""
import uuid

from sqlalchemy.orm import Session

from app.models import JobEvent, TrainingJob

TRANSITIONS: dict[str, set[str]] = {
    "QUEUED": {"PREPARING", "CANCELLED"},
    "PREPARING": {"RUNNING", "FAILED", "CANCELLED", "QUEUED"},
    "RUNNING": {"COMPLETED", "FAILED", "CANCELLED", "QUEUED"},
    "COMPLETED": set(),
    "FAILED": set(),
    "CANCELLED": set(),
}
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED"}
ACTIVE = {"QUEUED", "PREPARING", "RUNNING"}
STATUS_LABELS = {"QUEUED": "En cola", "PREPARING": "Preparando", "RUNNING": "Ejecutando",
                 "COMPLETED": "Completado", "FAILED": "Fallido", "CANCELLED": "Cancelado"}


class InvalidTransition(ValueError):
    pass


def can_transition(src: str, dst: str) -> bool:
    return dst in TRANSITIONS.get(src, set())


def transition(db: Session, job: TrainingJob, dst: str, **payload) -> None:
    if not can_transition(job.status, dst):
        raise InvalidTransition(f"Transición no permitida: {job.status} → {dst}")
    src = job.status
    job.status = dst
    emit(db, job.id, "status", {"from": src, "to": dst, "label": STATUS_LABELS[dst], **payload})


def emit(db: Session, job_id: uuid.UUID, event_type: str, payload: dict) -> None:
    db.add(JobEvent(job_id=job_id, event_type=event_type, payload=payload))


def job_public(job: TrainingJob) -> dict:
    return {
        "id": str(job.id), "project_id": str(job.project_id), "architecture_id": str(job.architecture_id),
        "dataset_id": str(job.dataset_id), "status": job.status, "status_label": STATUS_LABELS[job.status],
        "progress": round(job.progress, 4), "current_epoch": job.current_epoch, "total_epochs": job.total_epochs,
        "params": job.params_json, "attempt": job.attempt, "cancel_requested": job.cancel_requested,
        "cancel_reason": job.cancel_reason, "error_message": job.error_message, "result": job.result_json,
        "trace": job.trace_json, "created_by": str(job.created_by),
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "ended_at": job.ended_at.isoformat() if job.ended_at else None,
        "duration_seconds": (job.ended_at - job.started_at).total_seconds() if job.ended_at and job.started_at else None,
    }
