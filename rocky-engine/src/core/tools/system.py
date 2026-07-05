"""Herramientas de estado del sistema."""

from __future__ import annotations

from typing import Any

from src.domain.interfaces import BaseTool


class SystemStatusTool(BaseTool):
    """Estado del sistema con los datos reales de telemetría. Determinista:
    cero LLM, cero red — responde aunque Groq esté caído."""

    name = "system.status"
    description = (
        "system.status: el usuario pregunta cómo va el sistema, el estado "
        "actual de CPU, RAM, recursos o rendimiento del equipo."
    )

    async def run(
        self, args: dict[str, Any], telemetry: tuple[float, float] | None
    ) -> str:
        if telemetry is None:
            return "Aún no tengo telemetría, Sebas. Dame un segundo y vuelve a preguntar."

        cpu, ram = telemetry
        if cpu > 80.0 or ram > 90.0:
            verdict = "Vamos justos: considera cerrar algo pesado."
        elif cpu > 50.0 or ram > 70.0:
            verdict = "Carga moderada, nada preocupante."
        else:
            verdict = "Todo nominal."
        return f"CPU al {cpu:.0f}%, RAM al {ram:.0f}%. {verdict}"
