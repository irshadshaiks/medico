"""
Structured JSON logging with a request id on every line.

Deliberately scrubs anything that looks like a credential: log aggregation is
the easiest place in a healthcare system to leak a key by accident.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

_REDACT = ("api_key", "apikey", "password", "authorization", "secret", "token")


def _scrub(value: object) -> object:
    if isinstance(value, dict):
        return {
            k: ("***" if any(r in k.lower() for r in _REDACT) else _scrub(v)) for k, v in value.items()
        }
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get(),
        }
        extra = getattr(record, "extra", None)
        if isinstance(extra, dict):
            payload["extra"] = _scrub(extra)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(debug: bool = False) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    # These two are chatty and say nothing we don't already log ourselves.
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
