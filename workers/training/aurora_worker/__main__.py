"""Uso: PYTHONPATH=services/api:workers/training python -m aurora_worker"""
import signal
import sys
import threading
from pathlib import Path

try:
    import app  # noqa: F401
except ImportError:  # permite ejecutar desde la raíz del repo sin PYTHONPATH
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "services" / "api"))

from app.core.config import get_settings  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402
from app.core.migrate import run_migrations  # noqa: E402

setup_logging(get_settings().log_level)
run_migrations()

from aurora_worker.runner import run_loop  # noqa: E402

stop = threading.Event()
for sig in (signal.SIGTERM, signal.SIGINT):
    signal.signal(sig, lambda *_: stop.set())  # parada ordenada: termina el bucle tras el trabajo actual
run_loop(stop=stop, once="--once" in sys.argv)
