"""M05 Datasets: demos globales + CSV por proyecto (carga controlada, validación, versionado, borrado seguro)."""
import hashlib
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.common import iso, parse_uuid
from app.core.auth import get_current_user
from app.core.db import get_db
from app.core.permissions import Perm, authorize
from app.models import Dataset, TrainingJob, User
from app.modules.audit import record
from app.modules.datasets import BUILTINS, DatasetError, builtin_metadata, parse_csv, preview
from app.modules.jobs import ACTIVE
from app.modules.limits import effective_limits
from app.modules.storage import StorageError, get_storage

router = APIRouter(tags=["datasets"])


def dataset_out(d: Dataset) -> dict:
    m = d.metadata_json
    return {"id": str(d.id), "project_id": str(d.project_id) if d.project_id else None, "name": d.name,
            "version": d.version, "kind": d.kind, "family_hint": d.family_hint, "status": d.status,
            "task": m.get("task"), "input_shape": m.get("input_shape"), "num_classes": m.get("num_classes"),
            "samples": m.get("samples"), "class_names": m.get("class_names"), "feature_names": m.get("feature_names"),
            "description": m.get("description"), "split": m.get("split"), "size_bytes": m.get("size_bytes"),
            "sha256": m.get("sha256"), "created_at": iso(d.created_at)}


def seed_builtin_datasets(db: Session) -> None:
    existing = {d.metadata_json.get("builtin_key") for d in db.scalars(select(Dataset).where(Dataset.kind == "builtin"))}
    for key, b in BUILTINS.items():
        if key not in existing:
            db.add(Dataset(name=b["name"], kind="builtin", family_hint=b["family_hint"], metadata_json=builtin_metadata(key)))
    db.commit()


def get_dataset_for(db: Session, project_id: uuid.UUID, dataset_id: str) -> Dataset:
    d = db.get(Dataset, parse_uuid(dataset_id, "dataset"))
    if d is None or d.status != "ready" or (d.project_id is not None and d.project_id != project_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset no encontrado")
    return d


@router.get("/projects/{project_id}/datasets")
def list_datasets(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = authorize(db, parse_uuid(project_id, "proyecto"), user, Perm.VIEW)
    rows = db.scalars(select(Dataset).where(Dataset.status == "ready",
                                            or_(Dataset.project_id.is_(None), Dataset.project_id == p.id))
                      .order_by(Dataset.kind, Dataset.name, Dataset.version.desc())).all()
    return [dataset_out(d) for d in rows]


@router.get("/projects/{project_id}/datasets/{dataset_id}/preview")
def dataset_preview(project_id: str, dataset_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = authorize(db, parse_uuid(project_id, "proyecto"), user, Perm.VIEW)
    d = get_dataset_for(db, p.id, dataset_id)
    raw = get_storage().get(d.storage_key) if d.storage_key else None
    return {"dataset": dataset_out(d), **preview(d.metadata_json, raw)}


@router.post("/projects/{project_id}/datasets", status_code=201)
async def upload_dataset(project_id: str, name: str = Form(..., min_length=2, max_length=80),
                         target_column: str | None = Form(None, max_length=80), file: UploadFile = File(...),
                         user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = authorize(db, parse_uuid(project_id, "proyecto"), user, Perm.DESIGN)
    limits = effective_limits(db)
    max_bytes = int(limits["max_upload_mb"]) * 1024 * 1024
    if not (file.filename or "").lower().endswith((".csv", ".txt")):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Solo se admiten archivos .csv")
    raw = await file.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise HTTPException(413, f"El archivo supera {limits['max_upload_mb']} MB")
    try:
        meta = parse_csv(raw, (target_column or "").strip() or None)
    except DatasetError as exc:
        raise HTTPException(422, str(exc))
    version = (db.scalar(select(func.max(Dataset.version)).where(Dataset.project_id == p.id, Dataset.name == name)) or 0) + 1
    did = uuid.uuid4()
    key = f"datasets/{p.id}/{did}.csv"
    try:
        get_storage().put(key, raw, "text/csv")
    except StorageError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
    meta.update({"size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "original_filename": file.filename[:120]})
    d = Dataset(id=did, project_id=p.id, name=name, version=version, kind="upload", family_hint="feedforward",
                storage_key=key, metadata_json=meta, created_by=user.id)
    db.add(d)
    record(db, user.id, p.id, "dataset.uploaded", {"name": name, "version": version, "rows": meta["samples"]})
    db.commit()
    return dataset_out(d)


@router.delete("/projects/{project_id}/datasets/{dataset_id}")
def delete_dataset(project_id: str, dataset_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = authorize(db, parse_uuid(project_id, "proyecto"), user, Perm.EDIT_PROJECT)
    d = get_dataset_for(db, p.id, dataset_id)
    if d.kind == "builtin":
        raise HTTPException(status.HTTP_409_CONFLICT, "Los datasets demo no se pueden eliminar")
    busy = db.scalar(select(func.count()).select_from(TrainingJob)
                     .where(TrainingJob.dataset_id == d.id, TrainingJob.status.in_(ACTIVE)))
    if busy:
        raise HTTPException(status.HTTP_409_CONFLICT, "Hay entrenamientos activos que usan este dataset")
    # Borrado seguro: se elimina el archivo y se conserva la fila (trazabilidad de ejecuciones pasadas)
    if d.storage_key:
        get_storage().delete(d.storage_key)
    d.status = "deleted"
    record(db, user.id, p.id, "dataset.deleted", {"name": d.name, "version": d.version})
    db.commit()
    return {"ok": True}
