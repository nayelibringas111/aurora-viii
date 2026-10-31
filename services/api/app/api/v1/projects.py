"""M01 Dashboard · M02 Proyectos (miembros, permisos, estado) · auditoría por proyecto."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.common import iso, parse_uuid
from app.core.auth import get_current_user
from app.core.db import get_db
from app.core.permissions import ROLE_LABELS, Perm, authorize, member_role, permissions_for
from app.models import (Architecture, AuditEvent, ModelVersion, Project, ProjectMember, TrainingJob, User)
from app.modules.audit import record
from app.modules.jobs import ACTIVE, job_public
from app.schemas import MemberUpsert, ProjectCreate, ProjectUpdate, clean_tags

router = APIRouter(tags=["projects"])


def _accessible_ids(db: Session, user: User):
    if user.is_admin:
        return select(Project.id)
    return select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)


def project_out(db: Session, p: Project, user: User) -> dict:
    role = member_role(db, p.id, user)
    counts = db.execute(select(
        select(func.count()).select_from(Architecture).where(Architecture.project_id == p.id).scalar_subquery(),
        select(func.count()).select_from(TrainingJob).where(TrainingJob.project_id == p.id).scalar_subquery(),
        select(func.count()).select_from(ModelVersion).where(ModelVersion.project_id == p.id).scalar_subquery(),
        select(func.count()).select_from(ProjectMember).where(ProjectMember.project_id == p.id).scalar_subquery(),
    )).one()
    owner = db.get(User, p.owner_id)
    return {"id": str(p.id), "name": p.name, "description": p.description, "problem": p.problem, "tags": p.tags,
            "status": p.status, "owner": {"id": str(p.owner_id), "display_name": owner.display_name if owner else "—"},
            "created_at": iso(p.created_at), "updated_at": iso(p.updated_at),
            "my_role": role, "my_role_label": ROLE_LABELS.get(role or "", "—"),
            "my_permissions": sorted(p_.value for p_ in permissions_for(role)),
            "counts": {"architectures": counts[0], "jobs": counts[1], "models": counts[2], "members": counts[3]}}


@router.get("/projects")
def list_projects(q: str = Query("", max_length=100), status_: str = Query("active", alias="status"),
                  tag: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(Project).where(Project.id.in_(_accessible_ids(db, user)))
    if status_ in ("active", "archived"):
        stmt = stmt.where(Project.status == status_)
    if q:
        like = f"%{q.replace('%', '').replace('_', '')}%"
        stmt = stmt.where(or_(Project.name.ilike(like), Project.description.ilike(like)))
    if tag:
        stmt = stmt.where(Project.tags.contains([tag.lower()]))
    projects = db.scalars(stmt.order_by(Project.updated_at.desc()).limit(200)).all()
    return [project_out(db, p, user) for p in projects]


@router.post("/projects", status_code=201)
def create_project(body: ProjectCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = Project(id=uuid.uuid4(), name=body.name, description=body.description, problem=body.problem,
                tags=body.tags, owner_id=user.id)
    db.add(p)
    db.flush()
    db.add(ProjectMember(project_id=p.id, user_id=user.id, role="lead"))
    record(db, user.id, p.id, "project.created", {"name": p.name})
    db.commit()
    return project_out(db, p, user)


@router.get("/projects/{project_id}")
def get_project(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = authorize(db, parse_uuid(project_id, "proyecto"), user, Perm.VIEW)
    return project_out(db, p, user)


@router.patch("/projects/{project_id}")
def update_project(project_id: str, body: ProjectUpdate, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    p = authorize(db, parse_uuid(project_id, "proyecto"), user, Perm.EDIT_PROJECT)
    changes = body.model_dump(exclude_none=True)
    if "tags" in changes:
        changes["tags"] = clean_tags(changes["tags"])
    for k, v in changes.items():
        setattr(p, k, v)
    record(db, user.id, p.id, "project.updated", {"fields": sorted(changes)})
    db.commit()
    db.refresh(p)
    return project_out(db, p, user)


# ---------- Miembros ----------
@router.get("/projects/{project_id}/members")
def list_members(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = authorize(db, parse_uuid(project_id, "proyecto"), user, Perm.VIEW)
    rows = db.execute(select(ProjectMember, User).join(User, User.id == ProjectMember.user_id)
                      .where(ProjectMember.project_id == p.id).order_by(ProjectMember.added_at)).all()
    return [{"user_id": str(u.id), "email": u.email, "display_name": u.display_name, "role": m.role,
             "role_label": ROLE_LABELS[m.role], "added_at": iso(m.added_at), "is_owner": u.id == p.owner_id}
            for m, u in rows]


@router.put("/projects/{project_id}/members")
def upsert_member(project_id: str, body: MemberUpsert, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    p = authorize(db, parse_uuid(project_id, "proyecto"), user, Perm.MANAGE_MEMBERS)
    target = db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "Ese usuario aún no ha ingresado a Aurora VIII. Pídele que inicie sesión una vez.")
    if target.id == p.owner_id and body.role != "lead":
        raise HTTPException(status.HTTP_409_CONFLICT, "El propietario del proyecto siempre es Responsable")
    m = db.get(ProjectMember, (p.id, target.id))
    old = m.role if m else None
    if m:
        m.role = body.role
    else:
        db.add(ProjectMember(project_id=p.id, user_id=target.id, role=body.role))
    record(db, user.id, p.id, "member.role_changed", {"user": target.email, "from": old, "to": body.role})
    db.commit()
    return {"ok": True}


@router.delete("/projects/{project_id}/members/{user_id}")
def remove_member(project_id: str, user_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = authorize(db, parse_uuid(project_id, "proyecto"), user, Perm.MANAGE_MEMBERS)
    uid = parse_uuid(user_id, "usuario")
    if uid == p.owner_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "No se puede quitar al propietario")
    m = db.get(ProjectMember, (p.id, uid))
    if m:
        db.delete(m)
        record(db, user.id, p.id, "member.removed", {"user_id": str(uid)})
        db.commit()
    return {"ok": True}


# ---------- Auditoría ----------
@router.get("/projects/{project_id}/audit-events")
def project_audit(project_id: str, limit: int = Query(100, le=500), user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    p = authorize(db, parse_uuid(project_id, "proyecto"), user, Perm.VIEW_AUDIT)
    rows = db.execute(select(AuditEvent, User.display_name).outerjoin(User, User.id == AuditEvent.actor_id)
                      .where(AuditEvent.project_id == p.id).order_by(AuditEvent.id.desc()).limit(limit)).all()
    return [{"id": a.id, "action": a.action, "actor": name, "metadata": a.metadata_json, "created_at": iso(a.created_at)}
            for a, name in rows]


# ---------- Dashboard (M01) ----------
@router.get("/dashboard")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ids = _accessible_ids(db, user)
    n_projects = db.scalar(select(func.count()).select_from(Project).where(Project.id.in_(ids), Project.status == "active"))
    by_status = dict(db.execute(select(TrainingJob.status, func.count()).where(TrainingJob.project_id.in_(ids))
                                .group_by(TrainingJob.status)).all())
    n_models = db.scalar(select(func.count()).select_from(ModelVersion).where(ModelVersion.project_id.in_(ids)))
    approved = db.scalar(select(func.count()).select_from(ModelVersion)
                         .where(ModelVersion.project_id.in_(ids), ModelVersion.status == "approved"))
    recent = db.execute(select(TrainingJob, Project.name, Architecture.name, Architecture.family)
                        .join(Project, Project.id == TrainingJob.project_id)
                        .join(Architecture, Architecture.id == TrainingJob.architecture_id)
                        .where(TrainingJob.project_id.in_(ids)).order_by(TrainingJob.created_at.desc()).limit(12)).all()
    alerts = []
    failed = by_status.get("FAILED", 0)
    if failed:
        alerts.append({"level": "warning", "text": f"{failed} entrenamiento(s) fallido(s): revisa los mensajes de error"})
    stale = db.scalar(select(func.count()).select_from(TrainingJob).where(
        TrainingJob.project_id.in_(ids), TrainingJob.status == "QUEUED",
        TrainingJob.created_at < func.now() - func.make_interval(0, 0, 0, 0, 0, 10)))
    if stale:
        alerts.append({"level": "info", "text": f"{stale} trabajo(s) llevan más de 10 min en cola: ¿está activo el worker?"})
    return {
        "projects": n_projects, "jobs_by_status": by_status,
        "active_jobs": sum(v for k, v in by_status.items() if k in ACTIVE),
        "models": n_models, "approved_models": approved, "alerts": alerts,
        "recent_jobs": [{**job_public(j), "project_name": pn, "architecture_name": an, "family": fam}
                        for j, pn, an, fam in recent],
    }
