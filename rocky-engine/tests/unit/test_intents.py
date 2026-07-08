"""Tests del intent parser y el tool dispatcher."""

import pytest

from src.core.intent_parser import IntentParser
from src.core.tool_dispatcher import ToolDispatcher
from src.core.tools.system import SystemStatusTool, SystemTopTool
from src.domain.models import Intent, ProcessStat, SystemTelemetry
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


def t(cpu: float = 10.0, ram: float = 20.0, top: list | None = None) -> SystemTelemetry:
    return SystemTelemetry(cpu=cpu, ram=ram, top=top or [])


class TestToolDispatcher:
    @pytest.mark.asyncio
    async def test_chat_intent_returns_none(self) -> None:
        dispatcher = ToolDispatcher()
        assert await dispatcher.dispatch(Intent(tool="chat"), t()) is None

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_none(self) -> None:
        dispatcher = ToolDispatcher()
        assert await dispatcher.dispatch(Intent(tool="spotify.play"), None) is None

    @pytest.mark.asyncio
    async def test_system_status_uses_real_telemetry(self) -> None:
        dispatcher = ToolDispatcher()
        result = await dispatcher.dispatch(Intent(tool="system.status"), t(42.0, 61.0))
        assert result is not None
        assert "42" in result
        assert "61" in result

    @pytest.mark.asyncio
    async def test_system_status_without_telemetry(self) -> None:
        result = await SystemStatusTool().run({}, None)
        assert "telemetría" in result.lower()

    def test_tools_prompt_lists_tools_and_chat(self) -> None:
        prompt = ToolDispatcher().tools_prompt
        assert "system.status" in prompt
        assert "system.top" in prompt
        assert "chat" in prompt


class TestSystemTopTool:
    @pytest.mark.asyncio
    async def test_formats_top_processes(self) -> None:
        telemetry = t(
            top=[
                ProcessStat(name="chrome", cpu=41.0, mem_mb=2048.0),
                ProcessStat(name="cargo", cpu=22.0, mem_mb=512.0),
            ]
        )
        result = await SystemTopTool().run({}, telemetry)
        assert "chrome" in result
        assert "41% CPU" in result
        assert "cargo" in result

    @pytest.mark.asyncio
    async def test_without_process_data(self) -> None:
        assert "procesos" in (await SystemTopTool().run({}, t())).lower()
        assert "procesos" in (await SystemTopTool().run({}, None)).lower()
