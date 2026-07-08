"""Tool dispatcher: ejecuta el Intent validado contra el registro de herramientas.

Regla del blueprint: aquí no se interpreta lenguaje natural; se recibe un
schema ya validado y se ejecuta el adaptador correspondiente. `tool="chat"`
(o una herramienta desconocida) devuelve None: el orquestador cae a la
conversación libre con streaming.
"""

from __future__ import annotations

import logging

from src.core.tools.system import SystemStatusTool, SystemTopTool
from src.domain.interfaces import BaseTool
from src.domain.models import Intent, SystemTelemetry


class ToolDispatcher:
    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        self._logger = logging.getLogger("rocky.dispatcher")
        registry = tools if tools is not None else [SystemStatusTool(), SystemTopTool()]
        self._tools: dict[str, BaseTool] = {tool.name: tool for tool in registry}

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
            return None

        tool = self._tools.get(intent.tool)
        if tool is None:
            self._logger.warning("Herramienta desconocida: %s; cae a chat", intent.tool)
            return None

        try:
            return await tool.run(intent.args, telemetry)
        except Exception as exc:
            self._logger.warning("Herramienta %s falló: %s; cae a chat", intent.tool, exc)
            return None
