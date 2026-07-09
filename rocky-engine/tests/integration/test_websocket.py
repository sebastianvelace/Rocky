"""Tests del WebSocket local: handshake, telemetría y alertas."""

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

import pytest
from fastapi import FastAPI, status
from starlette.websockets import WebSocketDisconnect
from starlette.types import Message, Scope

os.environ.setdefault("ROCKY_AUTH_TOKEN", "test-token-123")

from src.api.middleware import RockySecurity
from src.api.websocket import create_ws_router
from src.core.analyzer import SystemAnalyzer
from src.orchestrator import RockyOrchestrator

AUTH_HEADERS = {"x-rocky-auth-token": "test-token-123"}
ASGIApp = Callable[
    [Scope, Callable[[], Awaitable[Message]], Callable[[Message], Awaitable[None]]],
    Awaitable[None],
]


class FakeGroqClient:
    fallback_text = "Sistema bajo carga, Sebas. Groq está offline."

    def __init__(self) -> None:
        self.selected_model: str | None = None

    def get_telemetry_advice(self, cpu: float, ram: float, resource: str = "cpu") -> str:
        return f"Alerta de {resource}: CPU {cpu:.0f}%, RAM {ram:.0f}%."

    def get_intent_json(self, user_text: str, tools_prompt: str) -> str | None:
        return None

    def stream_conversational_reply(
        self, user_text: str, telemetry: Any | None = None
    ) -> list[str]:
        return ["Respuesta ", "de prueba."]

    def status(self) -> dict[str, object]:
        return {
            "provider": "ollama" if self.selected_model else "groq",
            "active_model": self.selected_model or "llama-3.3-70b-versatile (Groq)",
            "models": [{"id": "qwen3:8b", "size_bytes": 4_000_000_000}],
            "detail": None,
        }

    def select_ollama_model(self, model: str) -> bool:
        if model != "qwen3:8b":
            return False
        self.selected_model = model
        return True


class FakeTTSManager:
    async def speak(self, text: str) -> None:
        return None


class FakeSTTManager:
    def listen_and_transcribe(self) -> str | None:
        return "hola rocky"


def build_app() -> tuple[FastAPI, RockyOrchestrator]:
    app = FastAPI()
    orchestrator = RockyOrchestrator(
        analyzer=SystemAnalyzer(),
        groq_client=FakeGroqClient(),  # type: ignore[arg-type]
        tts_manager=FakeTTSManager(),  # type: ignore[arg-type]
        stt_manager=FakeSTTManager(),  # type: ignore[arg-type]
    )
    app.include_router(create_ws_router(RockySecurity(), orchestrator))
    return app, orchestrator


class ASGIWebSocketSession:
    """Cliente WebSocket mínimo para probar la app ASGI sin Starlette TestClient.

    Starlette 1.x puede quedarse bloqueado en `TestClient.websocket_connect`
    con las versiones actuales de AnyIO/httpx. Este harness envía y recibe los
    mensajes ASGI directamente, que es suficiente para validar el contrato del
    endpoint `/ws` sin abrir puertos reales.
    """

    def __init__(self, app: ASGIApp, headers: dict[str, str] | None = None) -> None:
        self._app = app
        self._headers = headers or {}
        self._to_app: asyncio.Queue[Message] = asyncio.Queue()
        self._from_app: asyncio.Queue[Message] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> "ASGIWebSocketSession":
        scope: Scope = {
            "type": "websocket",
            "asgi": {"version": "3.0", "spec_version": "2.4"},
            "scheme": "ws",
            "path": "/ws",
            "raw_path": b"/ws",
            "query_string": b"",
            "root_path": "",
            "headers": [
                (key.lower().encode("latin-1"), value.encode("latin-1"))
                for key, value in self._headers.items()
            ],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "subprotocols": [],
            "state": {},
        }

        async def receive() -> Message:
            return await self._to_app.get()

        async def send(message: Message) -> None:
            await self._from_app.put(message)

        self._task = asyncio.create_task(self._app(scope, receive, send))
        await self._to_app.put({"type": "websocket.connect"})

        first = await self._from_app.get()
        if first["type"] != "websocket.accept":
            await self._raise_or_fail(first)
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self._to_app.put({"type": "websocket.disconnect", "code": 1000})
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=1.0)
            except TimeoutError:
                self._task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._task
        # El orquestador dispara TTS con `create_task`; dar un tick al loop
        # evita que asyncio cierre con una tarea ya completada pero no drenada.
        await asyncio.sleep(0)

    async def send_json(self, data: dict[str, Any] | str) -> None:
        text = data if isinstance(data, str) else json.dumps(data)
        await self._to_app.put({"type": "websocket.receive", "text": text})

    async def receive_json(self) -> dict[str, Any]:
        return json.loads(await self.receive_text())

    async def receive_text(self) -> str:
        message = await self._from_app.get()
        await self._raise_or_fail(message)
        if message["type"] != "websocket.send":
            raise AssertionError(f"Expected websocket.send, got {message!r}")
        return str(message.get("text", ""))

    async def _raise_or_fail(self, message: Message) -> None:
        if message["type"] == "websocket.close":
            raise WebSocketDisconnect(code=message.get("code", 1000))


@pytest.fixture()
def app() -> FastAPI:
    """App fresca por test: cooldown y contadores no se filtran entre tests."""
    app, _ = build_app()
    return app


@pytest.fixture(autouse=True)
def run_blocking_calls_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    async def inline_to_thread(func: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    def inline_run_in_executor(
        loop: asyncio.AbstractEventLoop,
        _executor: Any,
        func: Callable[..., Any],
        *args: Any,
    ) -> asyncio.Future[Any]:
        future: asyncio.Future[Any] = loop.create_future()
        try:
            future.set_result(func(*args))
        except Exception as exc:
            future.set_exception(exc)
        return future

    monkeypatch.setattr(asyncio, "to_thread", inline_to_thread)
    monkeypatch.setattr(asyncio.BaseEventLoop, "run_in_executor", inline_run_in_executor)


def ws_session(app: FastAPI, headers: dict[str, str] | None = None) -> ASGIWebSocketSession:
    return ASGIWebSocketSession(app, headers)


class TestHandshake:
    async def test_rejects_connection_without_token(self, app: FastAPI) -> None:
        async with ws_session(app) as ws:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                await ws.receive_text()
        assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION

    async def test_rejects_connection_with_wrong_token(self, app: FastAPI) -> None:
        async with ws_session(app, {"x-rocky-auth-token": "wrong"}) as ws:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                await ws.receive_text()
        assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION

    async def test_accepts_connection_with_token(self, app: FastAPI) -> None:
        async with ws_session(app, AUTH_HEADERS) as ws:
            await ws.send_json({"cpu": 10.0, "ram": 20.0})
            ack = await ws.receive_json()
            assert ack == {"status": "ok", "cpu_received": 10.0}


class TestTelemetryFlow:
    async def test_invalid_telemetry_is_ignored_not_fatal(self, app: FastAPI) -> None:
        async with ws_session(app, AUTH_HEADERS) as ws:
            await ws.send_json({"cpu": "not-a-number", "ram": 20.0})
            await ws.send_json("not even json")
            # La conexión sigue viva y responde a telemetría válida.
            await ws.send_json({"cpu": 5, "ram": 20})
            ack = await ws.receive_json()
            assert ack["status"] == "ok"

    async def test_sustained_high_cpu_produces_alert_with_message(
        self, app: FastAPI
    ) -> None:
        async with ws_session(app, AUTH_HEADERS) as ws:
            for _ in range(3):
                await ws.send_json({"cpu": 99.0, "ram": 20.0})

            messages = [await ws.receive_json() for _ in range(4)]
            acks = [m for m in messages if m.get("status") == "ok"]
            alerts = [m for m in messages if m.get("type") == "alert"]
            assert len(acks) == 3
            assert len(alerts) == 1
            # Sin GROQ_API_KEY el consejo cae al fallback, pero nunca vacío.
            assert alerts[0]["message"].strip() != ""
            assert alerts[0]["resource"] == "cpu"

    async def test_cooldown_suppresses_alerts_entirely(self, app: FastAPI) -> None:
        """Durante el cooldown no debe llegar NINGÚN mensaje de alerta (ni vacío)."""
        async with ws_session(app, AUTH_HEADERS) as ws:
            for _ in range(6):  # dos ventanas de 3 ticks sostenidos
                await ws.send_json({"cpu": 99.0, "ram": 20.0})
            # Centinela: al recibir su ack sabemos que todo lo anterior ya llegó.
            await ws.send_json({"cpu": 1.0, "ram": 20.0})

            alerts = []
            while True:
                message = await ws.receive_json()
                if message.get("cpu_received") == 1.0:
                    break
                if message.get("type") == "alert":
                    alerts.append(message)

            assert len(alerts) == 1  # la segunda queda silenciada por cooldown
            assert alerts[0]["message"].strip() != ""


class TestChatFlow:
    async def test_chat_action_echoes_user_and_replies(self, app: FastAPI) -> None:
        async with ws_session(app, AUTH_HEADERS) as ws:
            await ws.send_json({"action": "chat", "text": "hola rocky"})

            events = []
            while True:
                message = await ws.receive_json()
                events.append(message)
                if message.get("type") == "voice" and message.get("state") == "idle":
                    break

            chats = [e for e in events if e.get("type") == "chat"]
            states = [e["state"] for e in events if e.get("type") == "voice"]

            assert chats[0]["role"] == "user"
            assert chats[0]["text"] == "hola rocky"
            assert chats[0]["partial"] is False

            # Protocolo de streaming: ≥1 delta parcial y un final con el
            # texto completo (la concatenación de los deltas).
            partials = [c for c in chats[1:] if c["partial"]]
            finals = [c for c in chats[1:] if not c["partial"]]
            assert len(partials) >= 1
            assert len(finals) == 1
            assert all(c["role"] == "rocky" for c in chats[1:])
            # Sin GROQ_API_KEY responde el fallback, pero nunca vacío.
            assert finals[0]["text"].strip() != ""
            assert finals[0]["text"] == "".join(c["text"] for c in partials).strip()
            assert "thinking" in states

    async def test_empty_chat_text_is_ignored(self, app: FastAPI) -> None:
        async with ws_session(app, AUTH_HEADERS) as ws:
            await ws.send_json({"action": "chat", "text": "   "})
            # La conexión sigue viva: la telemetría posterior responde normal.
            await ws.send_json({"cpu": 5, "ram": 20})
            ack = await ws.receive_json()
            assert ack["status"] == "ok"

    async def test_chat_uses_latest_telemetry_as_context(self) -> None:
        """El orquestador cachea el último snapshot para dárselo al LLM."""
        app, orchestrator = build_app()
        async with ws_session(app, AUTH_HEADERS) as ws:
            await ws.send_json(
                {
                    "cpu": 42.0,
                    "ram": 33.0,
                    "top_cpu": [
                        {
                            "pid": "123",
                            "name": "cargo",
                            "cpu": 30,
                            "ram": 2,
                            "memory_mb": 512,
                        }
                    ],
                }
            )
            await ws.receive_json()  # ack
        assert orchestrator._last_telemetry is not None
        assert orchestrator._last_telemetry.cpu == 42.0
        assert orchestrator._last_telemetry.ram == 33.0
        assert orchestrator._last_telemetry.top_cpu[0].name == "cargo"


class TestModelFlow:
    async def test_lists_and_selects_local_models(self, app: FastAPI) -> None:
        async with ws_session(app, AUTH_HEADERS) as ws:
            await ws.send_json({"action": "models.list"})
            listed = await ws.receive_json()
            assert listed["type"] == "model-status"
            assert listed["models"][0]["id"] == "qwen3:8b"

            await ws.send_json({"action": "models.select", "model": "qwen3:8b"})
            selected = await ws.receive_json()
            assert selected["provider"] == "ollama"
            assert selected["active_model"] == "qwen3:8b"
