"""M06 Entrenamientos y M07 Evaluación: cola, cancelación, reintento, métricas y canal SSE.

REST es la fuente de verdad; el canal de eventos (SSE) solo empuja cambios. Si el navegador se
desconecta, al reconectar envía Last-Event-ID y recibe lo que se perdió desde la tabla job_events.
"""
import asyncio
import json
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.architectures import config_hash
from app.api.v1.common import parse_uuid
from app.api.v1.datasets import get_dataset_for
from app.core.auth import get_current_user
from app.core.db import SessionLocal, get_db
from app.core.permissions import Perm, authorize
from app.models import Architecture, Dataset, JobEvent, TrainingJob, TrainingMetric, User
from app.modules.architectures import compatibility
from app.modules.audit import record
from app.modules.jobs import ACTIVE, TERMINAL, emit, job_public, transition
from app.modules.limits import effective_limits
from app.schemas import CancelRequest, EvaluationNote, TrainingJobCreate

router = APIRouter(tags=["training"])
CODE_VERSION = os.getenv("RENDER_GIT_COMMIT") or os.getenv("GIT_COMMIT") or "dev"


def _job_for(db: Session, job_id: str, user: User, perm: Perm) -> TrainingJob:
    job = db.get(TrainingJob, parse_uuid(job_id, "entrenamiento"))
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entrenamiento no encontrado")
    authorize(db, job.project_id, user, perm)  # 404/403 si el proyecto es ajeno
    return job


def _enqueue(db: Session, user: User, project_id: uuid.UUID, arch: Architecture, ds: Dataset, params: dict,
             priority: int, retry_of: str | None = None) -> TrainingJob:
    limits = effective_limits(db)
    problems = compatibility(arch.family, arch.config_json, ds.metadata_json)
    if params["epochs"] > limits["max_epochs"]:
        problems.append(f"Máximo {limits['max_epochs']} épocas")
    if params["batch_size"] > limits["max_batch_size"]:
        problems.append(f"Batch máximo: {limits['max_batch_size']}")
    if problems:
        raise HTTPException(422, {"message": "No se puede iniciar", "issues": problems})
    mine = db.scalar(select(func.count()).select_from(TrainingJob)
                     .where(TrainingJob.created_by == user.id, TrainingJob.status.in_(ACTIVE)))
    if mine >= limits["max_concurrent_jobs_per_user"]:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Cuota alcanzada: máximo {limits['max_concurrent_jobs_per_user']} entrenamientos activos por usuario")
    queued = db.scalar(select(func.count()).select_from(TrainingJob)
                       .where(TrainingJob.project_id == project_id, TrainingJob.status == "QUEUED"))
    if queued >= limits["max_queued_jobs_per_project"]:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "La cola del proyecto está llena")
    # Prioridad por permisos: solo admins pueden priorizar por encima de 5
    priority = priority if user.is_admin else min(priority, 5)
    job = TrainingJob(
        id=uuid.uuid4(), project_id=project_id, architecture_id=arch.id, dataset_id=ds.id, status="QUEUED",
        total_epochs=params["epochs"] if arch.family != "gan" else params["epochs"], params_json=params,
        priority=priority, created_by=user.id,
        trace_json={"code_version": CODE_VERSION, "architecture": {"name": arch.name, "version": arch.version,
                                                                    "config_hash": config_hash(arch.config_json)},
                    "dataset": {"name": ds.name, "version": ds.version, "sha256": ds.metadata_json.get("sha256")},
                    "seed": params.get("seed"), "retry_of": retry_of,
                    "submitted_at": datetime.now(timezone.utc).isoformat()})
    db.add(job)
    db.flush()
    emit(db, job.id, "status", {"from": None, "to": "QUEUED", "label": "En cola"})
    record(db, user.id, project_id, "training.started" if not retry_of else "training.retried",
           {"job_id": str(job.id), "architecture": arch.name, "dataset": ds.name, **params})
    db.commit()
    return job


@router.post("/projects/{project_id}/training-jobs", status_code=202)
def create_job(project_id: str, body: TrainingJobCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = authorize(db, parse_uuid(project_id, "proyecto"), user, Perm.TRAIN)
    if p.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "El proyecto está archivado")
    arch = db.get(Architecture, parse_uuid(body.architecture_id, "arquitectura"))
    if arch is None or arch.project_id != p.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquitectura no encontrada")
    ds = get_dataset_for(db, p.id, body.dataset_id)
    job = _enqueue(db, user, p.id, arch, ds, body.params.model_dump(), body.priority)
    return {"job_id": str(job.id), **job_public(job)}


@router.get("/projects/{project_id}/training-jobs")
def list_jobs(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = authorize(db, parse_uuid(project_id, "proyecto"), user, Perm.VIEW)
    rows = db.execute(select(TrainingJob, Architecture.name, Architecture.family, Architecture.version, Dataset.name)
                      .join(Architecture, Architecture.id == TrainingJob.architecture_id)
                      .join(Dataset, Dataset.id == TrainingJob.dataset_id)
                      .where(TrainingJob.project_id == p.id).order_by(TrainingJob.created_at.desc()).limit(200)).all()
    return [{**job_public(j), "architecture_name": an, "family": fam, "architecture_version": av, "dataset_name": dn}
            for j, an, fam, av, dn in rows]


@router.get("/training-jobs/{job_id}")
def get_job(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _job_for(db, job_id, user, Perm.VIEW)
    arch = db.get(Architecture, job.architecture_id)
    ds = db.get(Dataset, job.dataset_id)
    last_event = db.scalar(select(func.max(JobEvent.id)).where(JobEvent.job_id == job.id)) or 0
    topology = db.scalar(select(JobEvent.payload).where(JobEvent.job_id == job.id, JobEvent.event_type == "topology")
                         .order_by(JobEvent.id.desc()).limit(1))
    snapshot = db.scalar(select(JobEvent.payload).where(JobEvent.job_id == job.id, JobEvent.event_type == "snapshot")
                         .order_by(JobEvent.id.desc()).limit(1))
    return {**job_public(job), "architecture": {"id": str(arch.id), "name": arch.name, "family": arch.family,
                                                "version": arch.version, "summary": arch.summary_json, "config": arch.config_json},
            "dataset": {"id": str(ds.id), "name": ds.name, "version": ds.version, "class_names": ds.metadata_json.get("class_names")},
            "topology": topology, "snapshot": snapshot, "last_event_id": last_event}


@router.get("/training-jobs/{job_id}/metrics")
def job_metrics(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _job_for(db, job_id, user, Perm.VIEW)
    rows = db.execute(select(TrainingMetric.epoch, TrainingMetric.metric_name, TrainingMetric.metric_value)
                      .where(TrainingMetric.job_id == job.id).order_by(TrainingMetric.epoch)).all()
    by_epoch: dict[int, dict] = {}
    for epoch, name, value in rows:
        by_epoch.setdefault(epoch, {"epoch": epoch})[name] = value
    return {"epochs": list(by_epoch.values()), "final": job.result_json.get("evaluation", {})}


@router.post("/training-jobs/{job_id}/cancel")
def cancel_job(job_id: str, body: CancelRequest | None = None, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    job = db.scalar(select(TrainingJob).where(TrainingJob.id == parse_uuid(job_id, "entrenamiento")).with_for_update())
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entrenamiento no encontrado")
    authorize(db, job.project_id, user, Perm.TRAIN)
    reason = (body.reason if body else "Cancelado por el usuario")
    if job.status in TERMINAL:
        raise HTTPException(status.HTTP_409_CONFLICT, f"El trabajo ya terminó ({job.status})")
    if job.status == "QUEUED":
        job.cancel_requested, job.cancel_reason = True, reason
        job.ended_at = datetime.now(timezone.utc)
        transition(db, job, "CANCELLED", reason=reason)
    else:
        # Cancelación cooperativa: el worker la detecta entre lotes y confirma el estado final
        job.cancel_requested, job.cancel_reason = True, reason
        emit(db, job.id, "cancel_requested", {"reason": reason})
    record(db, user.id, job.project_id, "training.cancel_requested", {"job_id": str(job.id), "reason": reason})
    db.commit()
    return job_public(job)


@router.post("/training-jobs/{job_id}/retry", status_code=202)
def retry_job(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _job_for(db, job_id, user, Perm.TRAIN)
    if job.status not in ("FAILED", "CANCELLED"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Solo se reintentan trabajos fallidos o cancelados")
    arch = db.get(Architecture, job.architecture_id)
    ds = get_dataset_for(db, job.project_id, str(job.dataset_id))
    new = _enqueue(db, user, job.project_id, arch, ds, job.params_json, job.priority, retry_of=str(job.id))
    return {"job_id": str(new.id), **job_public(new)}


@router.post("/training-jobs/{job_id}/notes")
def add_note(job_id: str, body: EvaluationNote, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Registro de limitaciones y observaciones de la evaluación (M07)."""
    job = _job_for(db, job_id, user, Perm.EXPORT)  # ingeniero, revisor o responsable
    notes = list(job.result_json.get("notes", []))
    notes.append({"author": user.display_name, "text": body.note, "at": datetime.now(timezone.utc).isoformat()})
    job.result_json = {**job.result_json, "notes": notes}
    record(db, user.id, job.project_id, "evaluation.note_added", {"job_id": str(job.id)})
    db.commit()
    return {"notes": notes}


@router.get("/training-jobs/{job_id}/events")
async def job_events(job_id: str, request: Request, after: int | None = Query(None),
                     user: User = Depends(get_current_user)):
    """Canal SSE autenticado. Reanuda desde Last-Event-ID (o ?after=) sin perder eventos."""
    def _check():
        with SessionLocal() as db:
            return _job_for(db, job_id, user, Perm.VIEW).id
    jid = await run_in_threadpool(_check)
    last_id = after
    header = request.headers.get("last-event-id")
    if header and header.isdigit():
        last_id = int(header)
    last_id = last_id or 0

    def _fetch(since: int):
        with SessionLocal() as db:
            evs = db.execute(select(JobEvent.id, JobEvent.event_type, JobEvent.payload, JobEvent.created_at)
                             .where(JobEvent.job_id == jid, JobEvent.id > since).order_by(JobEvent.id).limit(200)).all()
            st = db.scalar(select(TrainingJob.status).where(TrainingJob.id == jid))
            return evs, st

    async def stream():
        nonlocal last_id
        yield "retry: 2000\n\n"
        idle = 0.0
        while True:
            if await request.is_disconnected():
                break
            evs, st = await run_in_threadpool(_fetch, last_id)
            for eid, etype, payload, created in evs:
                last_id = eid
                data = json.dumps({"type": etype, "payload": payload, "at": created.isoformat()}, ensure_ascii=False)
                yield f"id: {eid}\nevent: {etype}\ndata: {data}\n\n"
            if evs:
                idle = 0.0
            elif st in TERMINAL:
                yield f"event: end\ndata: {json.dumps({'status': st})}\n\n"
                break
            else:
                idle += 0.4
                if idle >= 15:
                    idle = 0.0
                    yield ": keep-alive\n\n"
            await asyncio.sleep(0.4 if not evs else 0.05)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})
