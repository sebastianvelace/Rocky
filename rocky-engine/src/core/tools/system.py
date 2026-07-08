"""Herramientas de estado del sistema."""

from __future__ import annotations

from typing import Any

from src.domain.interfaces import BaseTool
from src.domain.models import ProcessTelemetry, SystemTelemetry


class SystemStatusTool(BaseTool):
    """Estado del sistema con los datos reales de telemetría. Determinista:
    cero LLM, cero red — responde aunque Groq esté caído."""

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
    """Lista los procesos principales por CPU y RAM usando telemetría real."""

    name = "system.top"
    description = (
        "system.top: el usuario pregunta qué proceso consume CPU, RAM, memoria, "
        "recursos o qué está pesado en el equipo."
    )

    async def run(
        self, args: dict[str, Any], telemetry: SystemTelemetry | None
    ) -> str:
        if telemetry is None:
            return "Aún no tengo procesos del sistema, Sebas. Dame un segundo."

        cpu_lines = self._format_rank("CPU", telemetry.top_cpu, "cpu")
        ram_lines = self._format_rank("RAM", telemetry.top_ram, "ram")
        if not cpu_lines and not ram_lines:
            return "No veo procesos relevantes ahora mismo. El sistema está tranquilo."

        parts = []
        if cpu_lines:
            parts.append("Top CPU:\n" + "\n".join(cpu_lines))
        if ram_lines:
            parts.append("Top RAM:\n" + "\n".join(ram_lines))
        return "\n\n".join(parts)

    def _format_rank(
        self, label: str, processes: list[ProcessTelemetry], metric: str
    ) -> list[str]:
        lines = []
        for idx, process in enumerate(processes[:5], start=1):
            value = process.cpu if metric == "cpu" else process.ram
            if label == "RAM":
                suffix = f"{value:.1f}% · {process.memory_mb:.0f} MB"
            else:
                suffix = f"{value:.1f}%"
            lines.append(f"{idx}. {process.name} (pid {process.pid}) — {suffix}")
        return lines
