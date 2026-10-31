"""Worker de entrenamiento Aurora VIII.

Cola en PostgreSQL (SELECT … FOR UPDATE SKIP LOCKED): varios workers pueden correr en paralelo sin
pisarse. Cada trabajo se ejecuta fuera de la petición HTTP; el estado, las métricas y los eventos se
persisten para que la interfaz los reciba por SSE y pueda recuperarse tras una reconexión.
"""
import hashlib
import logging
import os
import socket
import tempfile
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np  # noqa: E402
from sqlalchemy import func, select, update  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.models import (Architecture, Dataset, ModelVersion, SystemSetting, TrainingJob,  # noqa: E402
                        TrainingMetric)
from app.modules.datasets import load_arrays, split_arrays  # noqa: E402
from app.modules.jobs import emit, transition  # noqa: E402
from app.modules.limits import effective_limits  # noqa: E402
from app.modules.storage import get_storage  # noqa: E402

log = logging.getLogger("aurora.worker")
settings = get_settings()


class Cancelled(Exception):
    pass


class TimedOut(Exception):
    pass


def _now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- cola
def claim_next(worker_id: str) -> uuid.UUID | None:
    with SessionLocal() as db:
        job = db.scalar(select(TrainingJob).where(TrainingJob.status == "QUEUED")
                        .order_by(TrainingJob.priority.desc(), TrainingJob.created_at)
                        .with_for_update(skip_locked=True).limit(1))
        if job is None:
            return None
        job.attempt += 1
        job.worker_id = worker_id
        job.heartbeat_at = _now()
        transition(db, job, "PREPARING", worker=worker_id, attempt=job.attempt)
        db.commit()
        return job.id


def reclaim_stale() -> None:
    """Si un worker murió a mitad de un trabajo, se reencola (o falla si agotó los intentos)."""
    with SessionLocal() as db:
        cutoff = func.now() - func.make_interval(0, 0, 0, 0, 0, 0, settings.worker_stale_after_seconds)
        stale = db.scalars(select(TrainingJob).where(TrainingJob.status.in_(["PREPARING", "RUNNING"]),
                                                     TrainingJob.heartbeat_at < cutoff).with_for_update(skip_locked=True)).all()
        for job in stale:
            if job.cancel_requested:
                job.ended_at = _now()
                transition(db, job, "CANCELLED", reason=job.cancel_reason or "Cancelado")
            elif job.attempt < job.max_attempts:
                transition(db, job, "QUEUED", reason="El worker dejó de responder; se reintenta automáticamente")
                job.progress, job.current_epoch = 0.0, 0
                db.execute(TrainingMetric.__table__.delete().where(TrainingMetric.job_id == job.id))
            else:
                job.error_message = "El worker dejó de responder y se agotaron los reintentos"
                job.ended_at = _now()
                transition(db, job, "FAILED", error=job.error_message)
            log.warning("Trabajo %s recuperado tras worker caído → %s", job.id, job.status)
        db.commit()


# ---------------------------------------------------------------- emisión
class Reporter:
    """Escribe progreso/eventos en la BD con limitación de frecuencia y comprueba la cancelación."""

    def __init__(self, job_id: uuid.UUID, total_epochs: int, steps_per_epoch: int, timeout_s: int, observe: bool):
        self.job_id = job_id
        self.total = total_epochs
        self.steps = max(1, steps_per_epoch)
        self.timeout_s = timeout_s
        self.observe = observe
        self.t0 = time.monotonic()
        self.epoch_t0 = time.monotonic()
        self.last_progress = 0.0
        self.last_snapshot = 0.0
        self.last_cancel_check = 0.0
        self.epoch = 0

    def event(self, etype: str, payload: dict, **job_fields) -> None:
        with SessionLocal() as db:
            emit(db, self.job_id, etype, payload)
            if job_fields:
                job_fields["heartbeat_at"] = _now()
                db.execute(update(TrainingJob).where(TrainingJob.id == self.job_id).values(**job_fields))
            db.commit()

    def check(self) -> None:
        now = time.monotonic()
        if now - self.t0 > self.timeout_s:
            raise TimedOut()
        if now - self.last_cancel_check >= 0.8:
            self.last_cancel_check = now
            with SessionLocal() as db:
                if db.scalar(select(TrainingJob.cancel_requested).where(TrainingJob.id == self.job_id)):
                    raise Cancelled()

    def batch(self, step: int, logs: dict, snapshot_fn=None) -> None:
        now = time.monotonic()
        if now - self.last_progress >= 0.35:
            self.last_progress = now
            frac = (self.epoch + min(1.0, (step + 1) / self.steps)) / self.total
            self.event("progress", {"epoch": self.epoch + 1, "step": step + 1, "steps": self.steps,
                                    "progress": round(frac, 4), **{k: round(float(v), 5) for k, v in logs.items()}},
                       progress=frac)
        if snapshot_fn and now - self.last_snapshot >= 0.9:
            self.last_snapshot = now
            self.event("snapshot", snapshot_fn("batch"))
        self.check()

    def epoch_end(self, logs: dict, snapshot_fn=None) -> None:
        if self.observe:  # pacing mínimo para que la animación sea perceptible
            dt = time.monotonic() - self.epoch_t0
            if dt < 0.15:
                time.sleep(0.15 - dt)
        self.epoch += 1
        clean = {k: float(v) for k, v in logs.items() if np.isfinite(float(v))}
        if any(not np.isfinite(float(v)) for v in logs.values()):
            raise FloatingPointError("La pérdida se volvió NaN/infinito: reduce la tasa de aprendizaje")
        with SessionLocal() as db:
            for k, v in clean.items():
                db.add(TrainingMetric(job_id=self.job_id, epoch=self.epoch, metric_name=k, metric_value=v))
            emit(db, self.job_id, "epoch", {"epoch": self.epoch, "total": self.total, "progress": round(self.epoch / self.total, 4),
                                            "metrics": {k: round(v, 5) for k, v in clean.items()},
                                            "elapsed_s": round(time.monotonic() - self.t0, 2)})
            db.execute(update(TrainingJob).where(TrainingJob.id == self.job_id).values(
                current_epoch=self.epoch, progress=self.epoch / self.total, heartbeat_at=_now()))
            db.commit()
        now = time.monotonic()
        if snapshot_fn and (now - self.last_snapshot >= 0.45 or self.epoch == self.total):
            self.last_snapshot = now
            self.event("snapshot", snapshot_fn("epoch"))
        self.epoch_t0 = time.monotonic()
        self.check()


def _heartbeat_loop(job_id: uuid.UUID, worker_id: str, stop: threading.Event) -> None:
    while not stop.wait(settings.worker_heartbeat_seconds):
        try:
            with SessionLocal() as db:
                db.execute(update(TrainingJob).where(TrainingJob.id == job_id).values(heartbeat_at=_now()))
                db.commit()
        except Exception:  # noqa: BLE001
            log.warning("No se pudo registrar heartbeat", extra={"job_id": str(job_id)})


# ---------------------------------------------------------------- ejecución
def run_job(job_id: uuid.UUID, worker_id: str) -> None:
    import keras
    import tensorflow as tf

    from aurora_worker import trainers

    with SessionLocal() as db:
        job = db.get(TrainingJob, job_id)
        arch = db.get(Architecture, job.architecture_id)
        ds = db.get(Dataset, job.dataset_id)
        params, family, cfg = dict(job.params_json), arch.family, dict(arch.config_json)
        meta, storage_key, project_id = dict(ds.metadata_json), ds.storage_key, job.project_id
        timeout_s = int(effective_limits(db)["job_timeout_seconds"])
        total_epochs = job.total_epochs

    stop_hb = threading.Event()
    hb = threading.Thread(target=_heartbeat_loop, args=(job_id, worker_id, stop_hb), daemon=True)
    hb.start()
    rep = None
    try:
        seed = params.get("seed")
        if seed is not None:
            keras.utils.set_random_seed(int(seed))
        raw = get_storage().get(storage_key) if storage_key else None
        X, y = load_arrays(meta, raw, seed=seed or 7)
        (Xtr, ytr), (Xva, yva), (Xte, yte) = split_arrays(X, y)
        steps = int(np.ceil(len(Xtr) / params["batch_size"]))
        rep = Reporter(job_id, total_epochs, steps, timeout_s, params.get("observe", True))

        with SessionLocal() as db:
            j = db.get(TrainingJob, job_id)
            if j.cancel_requested:
                raise Cancelled()
            j.started_at = j.started_at or _now()
            j.trace_json = {**j.trace_json, "tensorflow": tf.__version__, "keras": keras.__version__,
                            "worker": worker_id, "samples": {"train": len(Xtr), "validation": len(Xva), "test": len(Xte)}}
            transition(db, j, "RUNNING")
            db.commit()

        if family == "gan":
            result, model_to_save = trainers.train_gan(cfg, params, Xtr, rep)
        else:
            result, model_to_save = trainers.train_classifier(cfg, params, meta, (Xtr, ytr), (Xva, yva), (Xte, yte), rep)

        # Registro del modelo: artefacto inmutable con checksum
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "modelo.keras"
            model_to_save.save(path)
            data = path.read_bytes()
        checksum = hashlib.sha256(data).hexdigest()
        key = f"models/{project_id}/{job_id}.keras"
        get_storage().put(key, data)
        with SessionLocal() as db:
            j = db.get(TrainingJob, job_id)
            version = (db.scalar(select(func.max(ModelVersion.version)).where(ModelVersion.project_id == project_id)) or 0) + 1
            mv = ModelVersion(project_id=project_id, job_id=job_id, version=version, storage_key=key, checksum=checksum,
                              size_bytes=len(data), metrics_json={k: v for k, v in result["evaluation"].items()
                                                                  if isinstance(v, (int, float))})
            db.add(mv)
            j.result_json = {**j.result_json, **result, "model_version": version, "checksum": checksum}
            j.progress, j.ended_at = 1.0, _now()
            transition(db, j, "COMPLETED", model_version=version, evaluation=result["evaluation"])
            db.commit()
        log.info("Entrenamiento completado", extra={"job_id": str(job_id)})

    except Cancelled:
        _finish(job_id, "CANCELLED", None)
    except TimedOut:
        _finish(job_id, "FAILED", f"Se superó el tiempo máximo de ejecución ({timeout_s} s)")
    except FloatingPointError as exc:
        _finish(job_id, "FAILED", str(exc))
    except MemoryError:
        _finish(job_id, "FAILED", "Memoria insuficiente: reduce el tamaño de la red o del batch")
    except Exception as exc:  # noqa: BLE001
        ref = uuid.uuid4().hex[:10]
        log.error("Fallo de entrenamiento ref=%s: %s\n%s", ref, exc, traceback.format_exc(), extra={"job_id": str(job_id)})
        _finish(job_id, "FAILED", f"Error técnico durante el entrenamiento (referencia {ref}). "
                                  "El detalle quedó en los logs protegidos del servidor.")
    finally:
        stop_hb.set()
        keras.backend.clear_session()


def _finish(job_id: uuid.UUID, status: str, error: str | None) -> None:
    with SessionLocal() as db:
        j = db.get(TrainingJob, job_id)
        if j.status in ("COMPLETED", "FAILED", "CANCELLED"):
            return
        j.ended_at = _now()
        if error:
            j.error_message = error
        if status == "CANCELLED":
            transition(db, j, "CANCELLED", reason=j.cancel_reason or "Cancelado", confirmed_by="worker")
        else:
            transition(db, j, "FAILED", error=error)
        db.commit()


def _beat(worker_id: str) -> None:
    with SessionLocal() as db:
        row = db.get(SystemSetting, "worker_heartbeat")
        val = {"worker_id": worker_id, "at": _now().isoformat(), "host": socket.gethostname()}
        if row:
            row.value_json = val
        else:
            db.add(SystemSetting(key="worker_heartbeat", value_json=val))
        db.commit()


def run_loop(stop: threading.Event | None = None, worker_id: str | None = None, once: bool = False) -> None:
    stop = stop or threading.Event()
    worker_id = worker_id or f"{socket.gethostname()}-{os.getpid()}"
    log.info("Worker %s escuchando la cola", worker_id)
    last_reclaim = 0.0
    last_beat = 0.0
    while not stop.is_set():
        try:
            now = time.monotonic()
            if now - last_reclaim > 30:
                reclaim_stale()
                last_reclaim = now
            if now - last_beat > 10:
                _beat(worker_id)
                last_beat = now
            job_id = claim_next(worker_id)
            if job_id:
                log.info("Trabajo tomado", extra={"job_id": str(job_id)})
                run_job(job_id, worker_id)
                if once:
                    return
                continue
            if once:
                return
        except Exception:  # noqa: BLE001
            log.exception("Error en el bucle del worker")
            time.sleep(3)
        stop.wait(settings.worker_poll_seconds)
