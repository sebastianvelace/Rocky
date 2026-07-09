"""Historial conversacional persistente (SQLite, stdlib).

La memoria de sesión vivía solo en RAM: reiniciar Rocky era amnesia total.
Este store guarda cada turno en ``~/.local/share/rocky/history.db`` (XDG)
y permite recargar los últimos al arrancar.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from pathlib import Path


def default_db_path() -> Path:
    base = os.getenv("XDG_DATA_HOME", "").strip() or str(Path.home() / ".local/share")
    return Path(base) / "rocky" / "history.db"


class HistoryStore:
    """Persistencia de turnos de conversación. Thread-safe (lock propio):
    el GroqClient la usa desde hilos de `asyncio.to_thread`."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._logger = logging.getLogger("rocky.history")
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        path = Path(db_path) if db_path is not None else default_db_path()

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(path), check_same_thread=False)
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL
                )
                """
            )
            self._conn.commit()
        except Exception as exc:
            # La persistencia es mejora, no requisito: sin disco, Rocky sigue.
            self._logger.warning("Historial persistente no disponible: %s", exc)
            self._conn = None

    def append(self, role: str, content: str) -> None:
        if self._conn is None or not content:
            return
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT INTO turns (ts, role, content) VALUES (?, ?, ?)",
                    (time.time(), role, content),
                )
                # La memoria útil es una ventana, no un log sin límite. Esto
                # evita crecimiento indefinido del SQLite en sesiones largas.
                self._conn.execute(
                    "DELETE FROM turns WHERE id NOT IN (SELECT id FROM turns ORDER BY id DESC LIMIT 1000)"
                )
                self._conn.commit()
        except Exception as exc:
            self._logger.warning("No se pudo persistir el turno: %s", exc)

    def load_recent(self, limit: int) -> list[dict[str, str]]:
        """Últimos `limit` turnos en orden cronológico, formato mensajes LLM."""
        if self._conn is None or limit <= 0:
            return []
        try:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT role, content FROM turns ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [{"role": role, "content": content} for role, content in reversed(rows)]
        except Exception as exc:
            self._logger.warning("No se pudo leer el historial: %s", exc)
            return []
