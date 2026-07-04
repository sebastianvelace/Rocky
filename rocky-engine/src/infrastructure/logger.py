"""Configuración central de logging (JSON, nivel vía ROCKY_LOG_LEVEL)."""

from __future__ import annotations

import json
import logging
import os


class JsonFormatter(logging.Formatter):
    """Logs en JSON por línea, sin dependencias externas."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        if record.exc_info:
            entry["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def configure_logging() -> None:
    """Configura el root logger una sola vez. Idempotente."""
    root = logging.getLogger()
    if root.handlers:
        return

    level_name = os.getenv("ROCKY_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)
