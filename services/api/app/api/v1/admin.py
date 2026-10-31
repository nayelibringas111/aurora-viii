"""M10 Administración y seguridad: usuarios, roles, auditoría global, límites, salud y retención."""
import time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.api.v1.common import iso, parse_uuid
from app.core.auth import require_admin
from app.core.config import get_settings
from app.core.db import get_db
from app.models import AuditEvent, JobEvent, Project, SystemSetting, TrainingJob, User
from app.modules.audit import record
from app.modules.jobs import TERMINAL
from app.modules.limits import BOUNDS, KEYS, effective_limits
from app.schemas import LimitsUpdate, UserAdminUpdate

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()


@router.get("/users")
def list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.scalars(select(User).order_by(User.created_at)).all()
    return [{"id": str(u.id), "email": u.email, "display_name": u.display_name, "is_admin": u.is_admin,
             "status": u.status, "created_at": iso(u.created_at)} for u in users]


@router.patch("/users/{user_id}")
def update_user(user_id: str, body: UserAdminUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.get(User, parse_uuid(user_id, "usuario"))
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    if u.id == admin.id and (body.is_admin is False or body.status == "suspended"):
        raise HTTPException(status.HTTP_409_CONFLICT, "No puedes quitarte tu propio rol de administrador ni suspenderte")
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(u, k, v)
    record(db, admin.id, None, "admin.user_updated", {"user": u.email, **changes})
    db.commit()
    return {"ok": True}


@router.get("/audit-events")
def global_audit(limit: int = Query(200, le=1000), action: str | None = None, admin: User = Depends(require_admin),
                 db: Session = Depends(get_db)):
    stmt = (select(AuditEvent, User.display_name, Project.name).outerjoin(User, User.id == AuditEvent.actor_id)
            .outerjoin(Project, Project.id == AuditEvent.project_id))
    if action:
        stmt = stmt.where(AuditEvent.action.ilike(f"{action.replace('%', '')}%"))
    rows = db.execute(stmt.order_by(AuditEvent.id.desc()).limit(limit)).all()
    return [{"id": a.id, "action": a.action, "actor": an, "project": pn, "metadata": a.metadata_json,
             "created_at": iso(a.created_at)} for a, an, pn in rows]


@router.get("/limits")
def get_limits(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {"values": effective_limits(db), "bounds": BOUNDS}


@router.put("/limits")
def put_limits(body: LimitsUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    for k, v in body.values.items():
        if k not in KEYS:
            raise HTTPException(422, f"Límite desconocido: {k}")
        lo, hi = BOUNDS[k]
        if not lo <= v <= hi:
            raise HTTPException(422, f"{k} debe estar entre {lo} y {hi}")
        row = db.get(SystemSetting, k)
        if row:
            row.value_json = v
        else:
            db.add(SystemSetting(key=k, value_json=v))
    record(db, admin.id, None, "admin.limits_updated", body.values)
    db.commit()
    return {"values": effective_limits(db)}


@router.get("/health")
def system_health(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    t0 = time.perf_counter()
    db.execute(text("SELECT 1"))
    db_ms = round((time.perf_counter() - t0) * 1000, 1)
    by_status = dict(db.execute(select(TrainingJob.status, func.count()).group_by(TrainingJob.status)).all())
    workers = db.execute(select(TrainingJob.worker_id, func.max(TrainingJob.heartbeat_at))
                         .where(TrainingJob.worker_id.isnot(None))
                         .group_by(TrainingJob.worker_id).order_by(func.max(TrainingJob.heartbeat_at).desc()).limit(10)).all()
    oldest_q = db.scalar(select(func.min(TrainingJob.created_at)).where(TrainingJob.status == "QUEUED"))
    beat = db.get(SystemSetting, "worker_heartbeat")
    return {"database": {"ok": True, "latency_ms": db_ms}, "jobs_by_status": by_status,
            "oldest_queued_at": iso(oldest_q), "workers": [{"id": w, "last_heartbeat": iso(h)} for w, h in workers],
            "worker_heartbeat": beat.value_json if beat else None,
            "config": {"environment": settings.environment, "auth_mode": settings.auth_mode,
                       "storage_backend": settings.storage_backend, "worker_in_process": settings.run_worker_in_process}}


@router.post("/retention/run")
def run_retention(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Elimina eventos de tiempo real de trabajos terminados más antiguos que event_retention_days.
    Métricas, resultados y auditoría se conservan."""
    days = int(effective_limits(db)["event_retention_days"])
    old_jobs = select(TrainingJob.id).where(TrainingJob.status.in_(TERMINAL),
                                            TrainingJob.ended_at < func.now() - func.make_interval(0, 0, 0, days))
    res = db.execute(delete(JobEvent).where(JobEvent.job_id.in_(old_jobs), JobEvent.event_type.in_(["progress", "snapshot", "batch"])))
    record(db, admin.id, None, "admin.retention_run", {"days": days, "deleted_events": res.rowcount})
    db.commit()
    return {"deleted_events": res.rowcount, "days": days}
