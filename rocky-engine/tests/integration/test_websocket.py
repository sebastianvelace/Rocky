"""Tests del WebSocket local: handshake, telemetría y alertas."""

import json
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("ROCKY_AUTH_TOKEN", "test-token-123")

from src.api.middleware import RockySecurity
from src.api.websocket import create_ws_router
from src.core.analyzer import SystemAnalyzer
from src.infrastructure.audio.stt_manager import STTManager
from src.infrastructure.audio.tts_manager import TTSManager
from src.infrastructure.clients.groq_client import GroqClient
from src.orchestrator import RockyOrchestrator

AUTH_HEADERS = {"x-rocky-auth-token": "test-token-123"}


def build_app() -> tuple[FastAPI, RockyOrchestrator]:
    app = FastAPI()
    orchestrator = RockyOrchestrator(
        analyzer=SystemAnalyzer(),
        groq_client=GroqClient(),
        tts_manager=TTSManager(),
        stt_manager=STTManager(),
    )
    app.include_router(create_ws_router(RockySecurity(), orchestrator))
    return app, orchestrator


@pytest.fixture()
def client() -> TestClient:
    """App fresca por test: el cooldown y los contadores no se filtran entre tests."""
    app, _ = build_app()
    return TestClient(app)


class TestHandshake:
    def test_rejects_connection_without_token(self, client: TestClient) -> None:
        with pytest.raises(Exception):
            with client.websocket_connect("/ws"):
                pass

    def test_rejects_connection_with_wrong_token(self, client: TestClient) -> None:
        with pytest.raises(Exception):
            with client.websocket_connect(
                "/ws", headers={"x-rocky-auth-token": "wrong"}
            ):
                pass

    def test_accepts_connection_with_token(self, client: TestClient) -> None:
        with client.websocket_connect("/ws", headers=AUTH_HEADERS) as ws:
            ws.send_text(json.dumps({"cpu": 10.0, "ram": 20.0}))
            ack = json.loads(ws.receive_text())
            assert ack == {"status": "ok", "cpu_received": 10.0}


class TestTelemetryFlow:
    def test_invalid_telemetry_is_ignored_not_fatal(self, client: TestClient) -> None:
        with client.websocket_connect("/ws", headers=AUTH_HEADERS) as ws:
            ws.send_text(json.dumps({"cpu": "not-a-number", "ram": 20.0}))
            ws.send_text("not even json")
            # La conexión sigue viva y responde a telemetría válida.
            ws.send_text(json.dumps({"cpu": 5, "ram": 20}))
            ack = json.loads(ws.receive_text())
            assert ack["status"] == "ok"

    def test_sustained_high_cpu_produces_alert_with_message(
        self, client: TestClient
    ) -> None:
        with client.websocket_connect("/ws", headers=AUTH_HEADERS) as ws:
            for _ in range(3):
                ws.send_text(json.dumps({"cpu": 99.0, "ram": 20.0}))

            messages = [json.loads(ws.receive_text()) for _ in range(4)]
            acks = [m for m in messages if m.get("status") == "ok"]
            alerts = [m for m in messages if m.get("type") == "alert"]
            assert len(acks) == 3
            assert len(alerts) == 1
            # Sin GROQ_API_KEY el consejo cae al fallback, pero nunca vacío.
            assert alerts[0]["message"].strip() != ""
            assert alerts[0]["resource"] == "cpu"

    def test_cooldown_suppresses_alerts_entirely(self, client: TestClient) -> None:
        """Durante el cooldown no debe llegar NINGÚN mensaje de alerta (ni vacío)."""
        with client.websocket_connect("/ws", headers=AUTH_HEADERS) as ws:
            for _ in range(6):  # dos ventanas de 3 ticks sostenidos
                ws.send_text(json.dumps({"cpu": 99.0, "ram": 20.0}))
            # Centinela: al recibir su ack sabemos que todo lo anterior ya llegó.
            ws.send_text(json.dumps({"cpu": 1.0, "ram": 20.0}))

            alerts = []
            while True:
                message = json.loads(ws.receive_text())
                if message.get("cpu_received") == 1.0:
                    break
                if message.get("type") == "alert":
                    alerts.append(message)

            assert len(alerts) == 1  # la segunda queda silenciada por cooldown
            assert alerts[0]["message"].strip() != ""


class TestChatFlow:
    def test_chat_action_echoes_user_and_replies(self, client: TestClient) -> None:
        with client.websocket_connect("/ws", headers=AUTH_HEADERS) as ws:
            ws.send_text(json.dumps({"action": "chat", "text": "hola rocky"}))

            events = []
            while True:
                message = json.loads(ws.receive_text())
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

    def test_empty_chat_text_is_ignored(self, client: TestClient) -> None:
        with client.websocket_connect("/ws", headers=AUTH_HEADERS) as ws:
            ws.send_text(json.dumps({"action": "chat", "text": "   "}))
            # La conexión sigue viva: la telemetría posterior responde normal.
            ws.send_text(json.dumps({"cpu": 5, "ram": 20}))
            ack = json.loads(ws.receive_text())
            assert ack["status"] == "ok"

    def test_chat_uses_latest_telemetry_as_context(self) -> None:
        """El orquestador cachea el último (cpu, ram) para dárselo al LLM."""
        app, orchestrator = build_app()
        client = TestClient(app)
        with client.websocket_connect("/ws", headers=AUTH_HEADERS) as ws:
            ws.send_text(
                json.dumps(
                    {
                        "cpu": 42.0,
                        "ram": 33.0,
                        "top": [{"name": "cargo", "cpu": 30, "mem_mb": 512}],
                    }
                )
            )
            json.loads(ws.receive_text())  # ack
        snapshot = orchestrator._last_telemetry
        assert snapshot is not None
        assert (snapshot.cpu, snapshot.ram) == (42.0, 33.0)
        assert snapshot.top[0].name == "cargo"
