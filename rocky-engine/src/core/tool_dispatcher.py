"""Tool dispatcher: ejecuta el Intent validado contra el registro de herramientas.

Regla del blueprint: aquí no se interpreta lenguaje natural; se recibe un
schema ya validado y se ejecuta el adaptador correspondiente. `tool="chat"`
(o una herramienta desconocida) devuelve None: el orquestador cae a la
conversación libre con streaming.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from src.core.tool_policy import ToolPolicy
from src.core.tools.system import SystemDiagnoseTool, SystemStatusTool, SystemTopTool
from src.domain.interfaces import BaseTool
from src.domain.models import Intent, SystemTelemetry


@dataclass(frozen=True)
class ToolExecution:
    tool: str
    capability: str
    status: str
    duration_ms: int = 0
    detail: str | None = None


class ToolDispatcher:
    def __init__(self, tools: list[BaseTool] | None = None, policy: ToolPolicy | None = None) -> None:
        self._logger = logging.getLogger("rocky.dispatcher")
        registry = (
            tools
            if tools is not None
            else [SystemStatusTool(), SystemTopTool(), SystemDiagnoseTool()]
        )
        self._tools: dict[str, BaseTool] = {tool.name: tool for tool in registry}
        self._policy = policy or ToolPolicy()
        self._last_execution: ToolExecution | None = None

    @property
    def last_execution(self) -> ToolExecution | None:
        return self._last_execution

    @property
    def tools_prompt(self) -> str:
        """Descripciones de las herramientas para el prompt del IntentParser."""
        lines = [f"- {tool.description}" for tool in self._tools.values()]
        lines.append("- chat: conversación general, cualquier otra cosa.")
        return "\n".join(lines)

    async def dispatch(
        self, intent: Intent, telemetry: SystemTelemetry | None
    ) -> str | None:
        """Ejecuta la herramienta del intent. None → que responda el chat."""
        if intent.tool == "chat":
            self._last_execution = None
            return None

        tool = self._tools.get(intent.tool)
        if tool is None:
            self._logger.warning("Herramienta desconocida: %s; cae a chat", intent.tool)
            self._last_execution = None
            return None

        decision = self._policy.decide(tool.capability)
        if not decision.allowed:
            self._last_execution = ToolExecution(
                tool=tool.name,
                capability=tool.capability,
                status="denied",
                detail=decision.reason,
            )
            return decision.reason

        started = time.perf_counter()
        try:
            result = await tool.run(intent.args, telemetry)
            self._last_execution = ToolExecution(
                tool=tool.name,
                capability=tool.capability,
                status="completed",
                duration_ms=round((time.perf_counter() - started) * 1000),
            )
            return result
        except Exception as exc:
            self._logger.warning("Herramienta %s falló: %s", intent.tool, exc)
            self._last_execution = ToolExecution(
                tool=tool.name,
                capability=tool.capability,
                status="failed",
                duration_ms=round((time.perf_counter() - started) * 1000),
                detail="La herramienta falló; revisa la configuración o reintenta.",
            )
            return self._last_execution.detail
