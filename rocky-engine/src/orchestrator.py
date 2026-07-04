"""Orquestador de Rocky: enruta mensajes entrantes hacia la capa correcta.

Sigue la regla del blueprint: el orquestador no hace el trabajo, solo decide
quién lo hace y mantiene el estado de sesión (cooldown de IA, pipeline de voz
en curso, serialización de envíos por el WebSocket).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import WebSocket
from pydantic import BaseModel, ValidationError

from src.core.analyzer import SystemAnalyzer
from src.domain.models import (
    AlertEvent,
    ChatEvent,
    SystemTelemetry,
    TelemetryAck,
    VoiceStateEvent,
)
from src.infrastructure.audio.stt_manager import STTManager
from src.infrastructure.audio.tts_manager import TTSManager
from src.infrastructure.clients.groq_client import GroqClient

# Cooldown para no pedir consejo a Groq (ni hablar) en cada tick mientras
# la sobrecarga sigue activa.
AI_COOLDOWN_SECONDS = 60.0


class RockyOrchestrator:
    def __init__(
        self,
        analyzer: SystemAnalyzer,
        groq_client: GroqClient,
        tts_manager: TTSManager,
        stt_manager: STTManager,
        ai_cooldown_seconds: float = AI_COOLDOWN_SECONDS,
    ) -> None:
        self._analyzer = analyzer
        self._groq = groq_client
        self._tts = tts_manager
        self._stt = stt_manager
        self._ai_cooldown_seconds = ai_cooldown_seconds
        self._last_ai_alert_time = 0.0
        self._voice_task: asyncio.Task[None] | None = None
        # Starlette no garantiza envíos concurrentes seguros sobre el mismo
        # socket; el pipeline de voz y la telemetría escriben en paralelo.
        self._send_lock = asyncio.Lock()
        self._logger = logging.getLogger("rocky.orchestrator")

    async def handle_message(self, websocket: WebSocket, data: Any) -> None:
        """Punto de entrada por cada mensaje JSON recibido del cliente (Rust)."""
        if not isinstance(data, dict):
            self._logger.error("[DATA] Mensaje no es un objeto JSON: %r", data)
            return

        if data.get("action") == "listen":
            self._spawn_voice_pipeline(websocket)
            return

        await self._handle_telemetry(websocket, data)

    async def _send(self, websocket: WebSocket, event: BaseModel) -> None:
        async with self._send_lock:
            await websocket.send_text(event.model_dump_json())

    # ------------------------------------------------------------------
    # Telemetría
    # ------------------------------------------------------------------
    async def _handle_telemetry(self, websocket: WebSocket, data: dict[str, Any]) -> None:
        try:
            model = SystemTelemetry.model_validate(data)
        except ValidationError as exc:
            self._logger.error("[DATA] Validación de telemetría fallida: %s", exc)
            return

        self._logger.debug(
            "[DATA] Telemetría validada: CPU=%s%% RAM=%s%%", model.cpu, model.ram
        )
        await self._send(websocket, TelemetryAck(status="ok", cpu_received=model.cpu))

        alert = self._analyzer.analyze(model)
        if alert is None:
            return

        now = time.monotonic()
        if (now - self._last_ai_alert_time) <= self._ai_cooldown_seconds:
            # En cooldown no se envía nada: mandar alertas con mensaje vacío
            # hacía parpadear un banner rojo sin contenido en la UI.
            self._logger.info("Alerta %s activa, pero IA en cooldown.", alert.resource)
            return

        self._last_ai_alert_time = now
        advice = await asyncio.to_thread(
            self._groq.get_telemetry_advice, model.cpu, model.ram, alert.resource
        )
        await self._send(
            websocket,
            AlertEvent(level="warning", resource=alert.resource, message=advice),
        )
        try:
            asyncio.get_running_loop().create_task(self._tts.speak(advice))
        except Exception as exc:
            self._logger.warning("No se pudo iniciar TTS: %s", exc)

    # ------------------------------------------------------------------
    # Voz
    # ------------------------------------------------------------------
    def _spawn_voice_pipeline(self, websocket: WebSocket) -> None:
        """Lanza el pipeline de voz como tarea para no bloquear la telemetría."""
        if self._voice_task is not None and not self._voice_task.done():
            self._logger.info("[VOICE] Pipeline ya en curso; se ignora la petición.")
            return
        self._voice_task = asyncio.get_running_loop().create_task(
            self._voice_pipeline(websocket)
        )

    async def _voice_pipeline(self, websocket: WebSocket) -> None:
        try:
            await self._send(websocket, VoiceStateEvent(state="listening"))
            user_text = await asyncio.to_thread(self._stt.listen_and_transcribe)

            if not user_text:
                await self._send(
                    websocket,
                    VoiceStateEvent(state="error", detail="No se capturó audio"),
                )
                return

            await self._send(websocket, ChatEvent(role="user", text=user_text))
            await self._send(websocket, VoiceStateEvent(state="thinking"))

            reply = await asyncio.to_thread(self._groq.get_conversational_reply, user_text)
            await self._send(websocket, ChatEvent(role="rocky", text=reply))

            await self._send(websocket, VoiceStateEvent(state="speaking"))
            await self._tts.speak(reply)
        except Exception as exc:
            self._logger.warning("[VOICE] Error en flujo STT/LLM/TTS: %s", exc)
            try:
                await self._send(websocket, VoiceStateEvent(state="error", detail=str(exc)))
            except Exception:
                pass
        finally:
            try:
                await self._send(websocket, VoiceStateEvent(state="idle"))
            except Exception:
                pass
