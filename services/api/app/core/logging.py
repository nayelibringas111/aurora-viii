"""Logs estructurados JSON. Nunca registramos tokens, contraseñas ni contenido de datasets."""
import json
import logging
import re
import sys
import time

_SECRET_RE = re.compile(r"(eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]+|access_token=[^&\s]+)")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        msg = _SECRET_RE.sub("[redactado]", record.getMessage())
        out = {"ts": round(time.time(), 3), "level": record.levelname, "logger": record.name, "msg": msg}
        for k in ("request_id", "user_id", "job_id", "path", "status", "ms"):
            if hasattr(record, k):
                out[k] = getattr(record, k)
        if record.exc_info:
            out["exc"] = _SECRET_RE.sub("[redactado]", self.formatException(record.exc_info))
        return json.dumps(out, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    for noisy in ("uvicorn.access", "httpx", "tensorflow", "absl"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
