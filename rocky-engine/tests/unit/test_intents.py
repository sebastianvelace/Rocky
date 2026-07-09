"""Tests del intent parser y el tool dispatcher."""

import pytest

from src.core.intent_parser import IntentParser
from src.core.tool_dispatcher import ToolDispatcher
from src.core.tools.system import SystemDiagnoseTool, SystemStatusTool, SystemTopTool
from src.domain.interfaces import BaseTool
from src.domain.models import Intent, SystemTelemetry
from src.infrastructure.clients.groq_client import GroqClient


class FakeGroq(GroqClient):
    """Devuelve un JSON fijo sin tocar la red."""

    def __init__(self, intent_json: str | None) -> None:
        super().__init__()
        self._intent_json = intent_json

    def get_intent_json(self, user_text: str, tools_prompt: str) -> str | None:
        return self._intent_json


class TestIntentParser:
    def test_without_groq_degrades_to_chat(self) -> None:
        parser = IntentParser(FakeGroq(None), tools_prompt="")
        assert parser.parse("hola").tool == "chat"

    def test_valid_json_produces_intent(self) -> None:
        parser = IntentParser(FakeGroq('{"tool": "system.status", "args": {}}'), "")
        intent = parser.parse("¿cómo va el sistema?")
        assert intent.tool == "system.status"
        assert intent.args == {}

    def test_malformed_json_degrades_to_chat(self) -> None:
        parser = IntentParser(FakeGroq("{esto no es json"), "")
        assert parser.parse("hola").tool == "chat"

    def test_wrong_schema_degrades_to_chat(self) -> None:
        # `extra="forbid"`: campos inesperados invalidan el intent.
        parser = IntentParser(FakeGroq('{"tool": "chat", "confidence": 0.9}'), "")
        assert parser.parse("hola").tool == "chat"

    def test_explicit_web_research_works_without_a_model(self) -> None:
        parser = IntentParser(FakeGroq(None), tools_prompt="")
        intent = parser.parse("Busca en internet las novedades de Python")
        assert intent.tool == "web.search"
        assert "Python" in intent.args["query"]

    def test_explicit_workspace_search_works_without_a_model(self) -> None:
        parser = IntentParser(FakeGroq(None), tools_prompt="")
        assert parser.parse("Busca en el repositorio dónde se valida el token").tool == "workspace.search"


def telemetry_with_processes(cpu: float = 10.0, ram: float = 20.0) -> SystemTelemetry:
    return SystemTelemetry.model_validate(
        {
            "cpu": cpu,
            "ram": ram,
            "top_cpu": [
                {
                    "pid": "123",
                    "name": "cargo",
                    "cpu": 36.5,
                    "ram": 1.1,
                    "memory_mb": 90,
                }
            ],
            "top_ram": [
                {
                    "pid": "456",
                    "name": "firefox",
                    "cpu": 5.0,
                    "ram": 12.2,
                    "memory_mb": 1400,
                }
            ],
        }
    )


class TestToolDispatcher:
    @pytest.mark.asyncio
    async def test_chat_intent_returns_none(self) -> None:
        dispatcher = ToolDispatcher()
        telemetry = SystemTelemetry(cpu=10.0, ram=20.0)
        assert await dispatcher.dispatch(Intent(tool="chat"), telemetry) is None

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_none(self) -> None:
        dispatcher = ToolDispatcher()
        assert await dispatcher.dispatch(Intent(tool="spotify.play"), None) is None

    @pytest.mark.asyncio
    async def test_system_status_uses_real_telemetry(self) -> None:
        dispatcher = ToolDispatcher()
        result = await dispatcher.dispatch(
            Intent(tool="system.status"), SystemTelemetry(cpu=42.0, ram=61.0)
        )
        assert result is not None
        assert "42" in result
        assert "61" in result

    @pytest.mark.asyncio
    async def test_system_status_without_telemetry(self) -> None:
        result = await SystemStatusTool().run({}, None)
        assert "telemetría" in result.lower()

    @pytest.mark.asyncio
    async def test_system_top_lists_process_rankings(self) -> None:
        telemetry = telemetry_with_processes()
        result = await SystemTopTool().run({}, telemetry)
        assert "Top CPU" in result
        assert "cargo" in result
        assert "Top RAM" in result
        assert "firefox" in result

    @pytest.mark.asyncio
    async def test_system_diagnose_recommends_ram_offender(self) -> None:
        telemetry = telemetry_with_processes(cpu=62.0, ram=94.0)
        result = await SystemDiagnoseTool().run({}, telemetry)
        assert "RAM" in result
        assert "firefox" in result
        assert "Prioridad" in result

    def test_tools_prompt_lists_tools_and_chat(self) -> None:
        prompt = ToolDispatcher().tools_prompt
        assert "system.status" in prompt
        assert "system.top" in prompt
        assert "system.diagnose" in prompt
        assert "chat" in prompt

    def test_tool_definitions_expose_only_declared_schema(self) -> None:
        definitions = ToolDispatcher().tool_definitions
        status = next(item for item in definitions if item["function"]["name"] == "system.status")
        assert status["function"]["parameters"]["additionalProperties"] is False

    @pytest.mark.asyncio
    async def test_denied_capability_never_runs_tool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class ExternalTool(BaseTool):
            name = "external.read"
            capability = "calendar.read"
            description = "external.read: test"
            called = False

            async def run(self, args, telemetry):  # type: ignore[no-untyped-def]
                self.called = True
                return "no debería ejecutarse"

        monkeypatch.setenv("ROCKY_ALLOW_CALENDAR_READ", "false")
        tool = ExternalTool()
        dispatcher = ToolDispatcher([tool])
        result = await dispatcher.dispatch(Intent(tool="external.read"), None)
        assert result is not None and "desactivada" in result
        assert tool.called is False
        assert dispatcher.last_execution is not None
        assert dispatcher.last_execution.status == "denied"


class TestSystemTopTool:
    @pytest.mark.asyncio
    async def test_formats_top_processes(self) -> None:
        telemetry = telemetry_with_processes()
        result = await SystemTopTool().run({}, telemetry)
        assert "cargo" in result
        assert "36.5%" in result
        assert "firefox" in result

    @pytest.mark.asyncio
    async def test_without_process_data(self) -> None:
        assert "procesos" in (
            await SystemTopTool().run({}, SystemTelemetry(cpu=10.0, ram=20.0))
        ).lower()
        assert "procesos" in (await SystemTopTool().run({}, None)).lower()
