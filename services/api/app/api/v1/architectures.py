"""M04 Diseñador de arquitecturas: validación en backend y versionado por nombre."""
import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.common import iso, parse_uuid
from app.core.auth import get_current_user
from app.core.db import get_db
from app.core.permissions import Perm, authorize
from app.models import Architecture, User
from app.modules.architectures import ArchitectureError, Limits, validate
from app.modules.audit import record
from app.modules.limits import effective_limits
from app.schemas import ArchitectureCreate, ArchitectureValidate

router = APIRouter(tags=["architectures"])


def _limits(db: Session) -> Limits:
    l = effective_limits(db)
    return Limits(max_layers=int(l["max_layers"]), max_units=int(l["max_units_per_layer"]), max_params=int(l["max_parameters"]))


def config_hash(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:16]


def arch_out(a: Architecture) -> dict:
    return {"id": str(a.id), "project_id": str(a.project_id), "name": a.name, "family": a.family,
            "justification": a.justification, "config": a.config_json, "summary": a.summary_json, "version": a.version,
            "config_hash": config_hash(a.config_json), "created_at": iso(a.created_at)}


@router.post("/architectures/validate")
def validate_architecture(body: ArchitectureValidate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        cfg, summary = validate(body.family, body.config, _limits(db))
        return {"valid": True, "config": cfg, "summary": summary, "issues": []}
    except ArchitectureError as exc:
        return {"valid": False, "issues": exc.issues}


@router.get("/projects/{project_id}/architectures")
def list_architectures(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = authorize(db, parse_uuid(project_id, "proyecto"), user, Perm.VIEW)
    rows = db.scalars(select(Architecture).where(Architecture.project_id == p.id)
                      .order_by(Architecture.created_at.desc())).all()
    return [arch_out(a) for a in rows]


@router.get("/projects/{project_id}/architectures/{arch_id}")
def get_architecture(project_id: str, arch_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = authorize(db, parse_uuid(project_id, "proyecto"), user, Perm.VIEW)
    a = db.get(Architecture, parse_uuid(arch_id, "arquitectura"))
    if a is None or a.project_id != p.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquitectura no encontrada")
    return arch_out(a)


@router.post("/projects/{project_id}/architectures", status_code=201)
def create_architecture(project_id: str, body: ArchitectureCreate, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    p = authorize(db, parse_uuid(project_id, "proyecto"), user, Perm.DESIGN)
    try:
        cfg, summary = validate(body.family, body.config, _limits(db))
    except ArchitectureError as exc:
        raise HTTPException(422, {"message": "Arquitectura inválida", "issues": exc.issues})
    version = (db.scalar(select(func.max(Architecture.version))
                         .where(Architecture.project_id == p.id, Architecture.name == body.name)) or 0) + 1
    a = Architecture(id=uuid.uuid4(), project_id=p.id, name=body.name, family=body.family,
                     justification=body.justification, config_json=cfg, summary_json=summary, version=version,
                     created_by=user.id)
    db.add(a)
    record(db, user.id, p.id, "architecture.created",
           {"name": a.name, "version": version, "family": a.family, "params": summary["total_params"]})
    db.commit()
    return arch_out(a)
