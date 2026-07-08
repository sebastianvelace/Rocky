"""Herramientas de estado del sistema. Deterministas: cero LLM, cero red."""

from __future__ import annotations

from typing import Any

from src.domain.interfaces import BaseTool
from src.domain.models import SystemTelemetry


class SystemStatusTool(BaseTool):
    """Estado global (CPU/RAM) con los datos reales de telemetría."""

    name = "system.status"
    description = (
        "system.status: el usuario pregunta cómo va el sistema, el estado "
        "actual de CPU, RAM, recursos o rendimiento del equipo."
    )

    async def run(
        self, args: dict[str, Any], telemetry: SystemTelemetry | None
    ) -> str:
        if telemetry is None:
            return "Aún no tengo telemetría, Sebas. Dame un segundo y vuelve a preguntar."

        cpu, ram = telemetry.cpu, telemetry.ram
        if cpu > 80.0 or ram > 90.0:
            verdict = "Vamos justos: considera cerrar algo pesado."
        elif cpu > 50.0 or ram > 70.0:
            verdict = "Carga moderada, nada preocupante."
        else:
            verdict = "Todo nominal."
        return f"CPU al {cpu:.0f}%, RAM al {ram:.0f}%. {verdict}"


class SystemTopTool(BaseTool):
    """Qué procesos consumen la máquina, con los datos que envía Rust."""

    name = "system.top"
    description = (
        "system.top: el usuario pregunta qué procesos consumen CPU o RAM, "
        "qué está comiendo la memoria, o pide el top de procesos."
    )

    async def run(
        self, args: dict[str, Any], telemetry: SystemTelemetry | None
    ) -> str:
        if telemetry is None or not telemetry.top:
            return (
                "Aún no tengo datos de procesos, Sebas. Dame un segundo y "
                "vuelve a preguntar."
            )

        lines = [
            f"• {p.name}: {p.cpu:.0f}% CPU, {p.mem_mb:,.0f} MB"
            for p in telemetry.top[:5]
        ]
        return "Esto es lo que más consume ahora mismo:\n" + "\n".join(lines)
