"""Arranca el worker de entrenamiento dentro del proceso de la API (RUN_WORKER_IN_PROCESS=true).

Pensado para el plan gratuito de Render (un único servicio web). Con carga real, usa el worker como
servicio separado (Render Background Worker) para aislar CPU y memoria del proceso HTTP.
"""
import logging
import sys
import threading
from pathlib import Path

log = logging.getLogger("aurora.api")


def start_embedded_worker(stop: threading.Event) -> None:
    try:
        from aurora_worker.runner import run_loop
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "workers" / "training"))
        from aurora_worker.runner import run_loop
    t = threading.Thread(target=run_loop, kwargs={"stop": stop, "worker_id": "embebido"}, daemon=True, name="aurora-worker")
    t.start()
    log.info("Worker de entrenamiento embebido iniciado")
