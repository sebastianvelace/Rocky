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
from src.core.intent_parser import IntentParser
from src.core.tool_dispatcher import ToolDispatcher
from src.domain.models import (
    AlertEvent,
    ChatEvent,
    ModelOption,
    ModelStatusEvent,
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
        dispatcher: ToolDispatcher | None = None,
        intent_parser: IntentParser | None = None,
    ) -> None:
        self._analyzer = analyzer
        self._groq = groq_client
        self._tts = tts_manager
        self._stt = stt_manager
        self._dispatcher = dispatcher or ToolDispatcher()
        self._parser = intent_parser or IntentParser(
            groq_client, self._dispatcher.tools_prompt
        )
        self._ai_cooldown_seconds = ai_cooldown_seconds
        self._last_ai_alert_time = 0.0
        # Último snapshot completo (cpu, ram, top de procesos): contexto para
        # las herramientas y para el LLM.
        self._last_telemetry: SystemTelemetry | None = None
        # Un solo pipeline interactivo (voz o chat) a la vez.
        self._active_task: asyncio.Task[None] | None = None
        # Starlette no garantiza envíos concurrentes seguros sobre el mismo
        # socket; el pipeline de voz y la telemetría escriben en paralelo.
        self._send_lock = asyncio.Lock()
        self._logger = logging.getLogger("rocky.orchestrator")

    async def handle_message(self, websocket: WebSocket, data: Any) -> None:
        """Punto de entrada por cada mensaje JSON recibido del cliente (Rust)."""
        if not isinstance(data, dict):
            self._logger.error("[DATA] Mensaje no es un objeto JSON: %r", data)
            return

        action = data.get("action")
        if action == "models.list":
            await self._send_model_status(websocket)
            return
        if action == "models.select":
            await self._select_model(websocket, str(data.get("model") or ""))
            return
        if action == "listen":
            self._spawn_exclusive(self._voice_pipeline(websocket))
            return
        if action == "chat":
            text = str(data.get("text") or "").strip()
            if text:
                self._spawn_exclusive(self._chat_pipeline(websocket, text))
            return

        await self._handle_telemetry(websocket, data)

    async def _send(self, websocket: WebSocket, event: BaseModel) -> None:
        async with self._send_lock:
            await websocket.send_text(event.model_dump_json())

    async def _send_model_status(self, websocket: WebSocket) -> None:
        status = await asyncio.to_thread(self._groq.status) if hasattr(self._groq, "status") else {}
        raw_models = status.get("models", []) if isinstance(status, dict) else []
        models = []
        for entry in raw_models:
            try:
                models.append(ModelOption.model_validate(entry))
            except ValidationError:
                continue
        provider = status.get("provider", "none") if isinstance(status, dict) else "none"
        if provider not in {"ollama", "groq", "none"}:
            provider = "none"
        await self._send(
            websocket,
            ModelStatusEvent(
                provider=provider,
                active_model=status.get("active_model") if isinstance(status, dict) else None,
                models=models,
                detail=status.get("detail") if isinstance(status, dict) else None,
            ),
        )

    async def _select_model(self, websocket: WebSocket, model: str) -> None:
        selected = False
        if hasattr(self._groq, "select_ollama_model"):
            selected = await asyncio.to_thread(self._groq.select_ollama_model, model)
        if not selected:
            self._logger.warning("Selección de modelo rechazada: %s", model)
        await self._send_model_status(websocket)

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
        self._last_telemetry = model
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
    # Voz y chat
    # ------------------------------------------------------------------
    def _spawn_exclusive(self, coro: Any) -> None:
        """Lanza un pipeline interactivo como tarea (la telemetría no se bloquea).

        Solo uno a la vez: si ya hay voz o chat en curso, la petición se ignora
        (la UI deshabilita los controles, esto es la red de seguridad).
        """
        if self._active_task is not None and not self._active_task.done():
            self._logger.info("[PIPELINE] Ya hay uno en curso; se ignora la petición.")
            coro.close()
            return
        self._active_task = asyncio.get_running_loop().create_task(coro)

    async def _respond(self, websocket: WebSocket, text: str) -> str:
        """Parsea la intención y responde: herramienta determinista si aplica,
        conversación libre (streaming) en cualquier otro caso."""
        intent = await asyncio.to_thread(self._parser.parse, text)
        tool_result = await self._dispatcher.dispatch(intent, self._last_telemetry)
        if tool_result is not None:
            await self._send(websocket, ChatEvent(role="rocky", text=tool_result))
            return tool_result
        return await self._stream_reply(websocket, text)

    async def _stream_reply(self, websocket: WebSocket, text: str) -> str:
        """Streaming del LLM → deltas `ChatEvent(partial=True)` → texto final.

        El generador de Groq es bloqueante: corre en un hilo y empuja los
        deltas a una cola del event loop para no congelar la telemetría.
        """
        # Backpressure real: si la UI/socket se ralentiza, el hilo productor
        # espera en vez de acumular una respuesta larga completa en RAM.
        queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=32)
        loop = asyncio.get_running_loop()

        def enqueue(item: str | None) -> None:
            try:
                # En producción `producer` corre en un worker: bloquear aquí
                # propaga presión de vuelta al cliente de streaming.
                asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run_coroutine_threadsafe(queue.put(item), loop).result()
            else:
                # El harness ASGI ejecuta el executor inline; esperar a la
                # misma cola en ese caso bloquearía el loop de pruebas.
                loop.call_soon(queue.put_nowait, item)

        def producer() -> None:
            try:
                for delta in self._groq.stream_conversational_reply(
                    text, self._telemetry_context()
                ):
                    enqueue(delta)
            finally:
                enqueue(None)

        producer_future = loop.run_in_executor(None, producer)

        parts: list[str] = []
        while True:
            delta = await queue.get()
            if delta is None:
                break
            parts.append(delta)
            await self._send(websocket, ChatEvent(role="rocky", text=delta, partial=True))
        await producer_future

        full = "".join(parts).strip() or self._groq.fallback_text
        # Evento final: texto completo, cierra el mensaje en la UI.
        await self._send(websocket, ChatEvent(role="rocky", text=full))
        return full

    def _telemetry_context(self) -> SystemTelemetry | None:
        return self._last_telemetry

    async def _chat_pipeline(self, websocket: WebSocket, text: str) -> None:
        """Chat por texto: eco del usuario → LLM (streaming) → respuesta.
        Sin TTS (si Sebas escribe en vez de hablar, asumimos que no quiere
        audio)."""
        try:
            await self._send(websocket, ChatEvent(role="user", text=text))
            await self._send(websocket, VoiceStateEvent(state="thinking"))
            await self._respond(websocket, text)
        except Exception as exc:
            self._logger.warning("[CHAT] Error en flujo LLM: %s", exc)
            try:
                await self._send(websocket, VoiceStateEvent(state="error", detail=str(exc)))
            except Exception:
                pass
        finally:
            try:
                await self._send(websocket, VoiceStateEvent(state="idle"))
            except Exception:
                pass

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

            reply = await self._respond(websocket, user_text)

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
