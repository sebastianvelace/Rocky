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


class SystemDiagnoseTool(BaseTool):
    """Diagnóstico accionable de recursos, sin LLM ni red."""

    name = "system.diagnose"
    description = (
        "system.diagnose: el usuario pide diagnóstico, recomendación, qué cerrar, "
        "por qué está lento el equipo o cuál es el cuello de botella."
    )

    async def run(
        self, args: dict[str, Any], telemetry: SystemTelemetry | None
    ) -> str:
        if telemetry is None:
            return "Aún no tengo suficiente telemetría para diagnosticar, Sebas."

        cpu_hot = telemetry.cpu > 80.0
        ram_hot = telemetry.ram > 90.0
        cpu_warm = telemetry.cpu > 55.0
        ram_warm = telemetry.ram > 75.0

        top_cpu = telemetry.top_cpu[0] if telemetry.top_cpu else None
        top_ram = telemetry.top_ram[0] if telemetry.top_ram else None

        if cpu_hot and ram_hot:
            summary = "Cuello de botella mixto: CPU y RAM están altos."
        elif ram_hot:
            summary = "El cuello de botella principal parece RAM."
        elif cpu_hot:
            summary = "El cuello de botella principal parece CPU."
        elif cpu_warm or ram_warm:
            summary = "Hay carga moderada, pero no parece una emergencia."
        else:
            summary = "No veo presión relevante: el sistema está estable."

        findings = []
        if top_cpu is not None and top_cpu.cpu >= 10.0:
            findings.append(
                f"CPU: {top_cpu.name} (pid {top_cpu.pid}) usa {top_cpu.cpu:.1f}%."
            )
        if top_ram is not None and (top_ram.ram >= 5.0 or top_ram.memory_mb >= 500.0):
            findings.append(
                f"RAM: {top_ram.name} (pid {top_ram.pid}) usa "
                f"{top_ram.ram:.1f}% ({top_ram.memory_mb:.0f} MB)."
            )

        recommendation = self._recommendation(
            telemetry, top_cpu=top_cpu, top_ram=top_ram, cpu_hot=cpu_hot, ram_hot=ram_hot
        )
        detail = " ".join(findings) if findings else "No hay un proceso claramente dominante."
        return f"{summary} {detail} {recommendation}"

    def _recommendation(
        self,
        telemetry: SystemTelemetry,
        *,
        top_cpu: ProcessTelemetry | None,
        top_ram: ProcessTelemetry | None,
        cpu_hot: bool,
        ram_hot: bool,
    ) -> str:
        if ram_hot and top_ram is not None:
            return (
                f"Prioridad: revisa {top_ram.name}; si no es crítico, ciérralo desde la UI."
            )
        if cpu_hot and top_cpu is not None:
            return (
                f"Prioridad: revisa {top_cpu.name}; está concentrando CPU ahora mismo."
            )
        if telemetry.ram > 75.0 and top_ram is not None:
            return f"Vigila {top_ram.name}; la RAM va subiendo, pero aún hay margen."
        if telemetry.cpu > 55.0 and top_cpu is not None:
            return f"Vigila {top_cpu.name}; la CPU está activa, pero controlada."
        return "No cerraría nada por ahora."
