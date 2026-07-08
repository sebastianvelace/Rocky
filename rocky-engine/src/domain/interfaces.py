"""Interfaces del dominio (contratos que implementa la infraestructura)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from src.domain.models import SystemTelemetry


class BaseTool(ABC):
    """Herramienta determinista ejecutable por el ToolDispatcher.

    `name` es el identificador que emite el intent parser; `description`
    se inyecta al prompt de clasificación (una línea, en español, que
    describa cuándo aplicar la herramienta).
    """

    name: ClassVar[str]
    description: ClassVar[str]

    @abstractmethod
    async def run(
        self, args: dict[str, Any], telemetry: "SystemTelemetry | None"
    ) -> str:
        """Ejecuta la herramienta y devuelve el texto de respuesta para el usuario.

        `telemetry` es el último snapshot completo (cpu, ram, top de
        procesos) o None si aún no llegó ninguno.
        """
