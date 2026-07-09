"""Búsqueda local de solo lectura, confinada al workspace configurado."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.domain.interfaces import BaseTool
from src.domain.models import SystemTelemetry


class LocalWorkspaceSearchTool(BaseTool):
    name = "workspace.search"
    description = "workspace.search: busca texto o archivos en el workspace local del usuario, repositorio o código local. args: {query}."
    _EXCLUDED = {".git", ".next", "node_modules", "venv", "__pycache__", ".pytest_cache"}
    _MAX_FILES = 6
    _MAX_FILE_BYTES = 256_000

    def _root(self) -> Path:
        configured = os.getenv("ROCKY_WORKSPACE_ROOT", "").strip()
        return Path(configured).expanduser().resolve() if configured else Path.cwd().parent.resolve()

    async def run(self, args: dict[str, Any], telemetry: SystemTelemetry | None) -> str:
        query = str(args.get("query", "")).strip()
        if len(query) < 2:
            return "Indica al menos dos caracteres para buscar en el workspace local."
        root = self._root()
        if not root.is_dir():
            return "La raíz del workspace local no está disponible."

        matches: list[str] = []
        needle = query.casefold()
        for directory, dirs, files in os.walk(root):
            dirs[:] = [name for name in dirs if name not in self._EXCLUDED and not name.startswith(".")]
            for filename in files:
                path = Path(directory) / filename
                try:
                    if path.stat().st_size > self._MAX_FILE_BYTES:
                        continue
                    relative = path.relative_to(root)
                    if needle in str(relative).casefold():
                        matches.append(f"{relative} (nombre)")
                    elif path.suffix.lower() in {".py", ".rs", ".ts", ".tsx", ".md", ".json", ".toml", ".yml", ".yaml", ".txt"}:
                        content = path.read_text(encoding="utf-8", errors="ignore")
                        if needle in content.casefold():
                            matches.append(f"{relative} (contenido)")
                except OSError:
                    continue
                if len(matches) >= self._MAX_FILES:
                    return "Coincidencias locales:\n" + "\n".join(f"- {item}" for item in matches)
        return "Coincidencias locales:\n" + "\n".join(f"- {item}" for item in matches) if matches else "No encontré coincidencias en el workspace permitido."
