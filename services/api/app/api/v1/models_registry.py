"""M08 Registro de modelos: versiones inmutables, flujo borrador → revisado → aprobado → retirado."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.common import iso, parse_uuid
from app.core.auth import get_current_user
from app.core.db import get_db
from app.core.permissions import Perm, authorize
from app.models import Architecture, ModelVersion, TrainingJob, User
from app.modules.audit import record
from app.modules.storage import StorageError, get_storage
from app.schemas import ModelStatusUpdate

router = APIRouter(tags=["models"])

FLOW = {"draft": {"reviewed", "retired"}, "reviewed": {"approved", "retired"}, "approved": {"retired"}, "retired": set()}
STATUS_LABELS = {"draft": "Borrador", "reviewed": "Revisado", "approved": "Aprobado", "retired": "Retirado"}


def model_out(m: ModelVersion, arch: Architecture | None = None, job: TrainingJob | None = None) -> dict:
    return {"id": str(m.id), "project_id": str(m.project_id), "job_id": str(m.job_id), "version": m.version,
            "status": m.status, "status_label": STATUS_LABELS[m.status], "checksum": m.checksum, "size_bytes": m.size_bytes,
            "metrics": m.metrics_json, "notes": m.notes, "created_at": iso(m.created_at),
            "architecture": {"name": arch.name, "family": arch.family, "version": arch.version} if arch else None,
            "params": job.params_json if job else None, "trace": job.trace_json if job else None}


def _model_for(db: Session, model_id: str, user: User, perm: Perm) -> ModelVersion:
    m = db.get(ModelVersion, parse_uuid(model_id, "modelo"))
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Modelo no encontrado")
    authorize(db, m.project_id, user, perm)
    return m


@router.get("/projects/{project_id}/models")
def list_models(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = authorize(db, parse_uuid(project_id, "proyecto"), user, Perm.VIEW)
    rows = db.execute(select(ModelVersion, Architecture, TrainingJob)
                      .join(TrainingJob, TrainingJob.id == ModelVersion.job_id)
                      .join(Architecture, Architecture.id == TrainingJob.architecture_id)
                      .where(ModelVersion.project_id == p.id).order_by(ModelVersion.version.desc())).all()
    return [model_out(m, a, j) for m, a, j in rows]


@router.patch("/models/{model_id}/status")
def change_status(model_id: str, body: ModelStatusUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    perm = Perm.RETIRE_MODEL if body.status == "retired" else Perm.REVIEW_MODEL
    m = _model_for(db, model_id, user, perm)
    if body.status not in FLOW[m.status]:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"No se puede pasar de {STATUS_LABELS[m.status]} a {STATUS_LABELS[body.status]}")
    old = m.status
    m.status = body.status
    if body.notes:
        m.notes = (m.notes + "\n" if m.notes else "") + f"[{STATUS_LABELS[body.status]} · {user.display_name}] {body.notes}"
    record(db, user.id, m.project_id, "model.status_changed", {"model_version": m.version, "from": old, "to": body.status})
    db.commit()
    return model_out(m)


@router.get("/models/{model_id}/download")
def download_model(model_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = _model_for(db, model_id, user, Perm.DOWNLOAD_MODEL)
    try:
        data = get_storage().get(m.storage_key)
    except StorageError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
    record(db, user.id, m.project_id, "model.exported", {"model_version": m.version})
    db.commit()
    return Response(data, media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="aurora-viii-modelo-v{m.version}.keras"',
                             "X-Checksum-SHA256": m.checksum})
