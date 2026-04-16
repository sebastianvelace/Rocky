import json
import logging
import time
import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from src.api.middleware import RockySecurity
from src.core.analyzer import SystemAnalyzer
from src.domain.models import SystemTelemetry, TelemetryAck
from src.infrastructure.clients.groq_client import GroqClient
from src.infrastructure.audio.tts_manager import TTSManager
from src.infrastructure.audio.stt_manager import STTManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

# Cooldown para evitar spam de Groq mientras la alerta está activa.
AI_COOLDOWN_SECONDS = 60
last_ai_alert_time = 0.0

# Carga opcional de variables desde .env (si existe y está instalado python-dotenv).
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(override=False)
except Exception:
    pass

app = FastAPI(title="Rocky Handshake Backend")
security = RockySecurity()
ws_logger = logging.getLogger("rocky.ws")
analyzer = SystemAnalyzer()
groq_client = GroqClient()
tts_manager = TTSManager()
stt_manager = STTManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    global last_ai_alert_time

    is_valid = await security.validate_websocket(websocket)
    if not is_valid:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    ws_logger.info("WebSocket connected")

    try:
        while True:
            payload = await websocket.receive_text()
            try:
                data = json.loads(payload)
            except json.JSONDecodeError as exc:
                ws_logger.error("[DATA] JSON inválido: %s", exc)
                continue

            # Acciones de control (voz)
            if isinstance(data, dict) and data.get("action") == "listen":
                try:
                    user_text = await asyncio.to_thread(stt_manager.listen_and_transcribe)
                    if user_text:
                        reply = await asyncio.to_thread(
                            groq_client.get_conversational_reply, user_text
                        )
                        asyncio.create_task(tts_manager.speak(reply))
                except Exception as exc:
                    ws_logger.warning("[VOICE] Error en flujo STT/LLM/TTS: %s", exc)
                continue

            # Telemetría normal
            try:
                model = SystemTelemetry.model_validate(data)
            except ValidationError as exc:
                ws_logger.error("[DATA] Validación de telemetría fallida: %s", exc)
                continue

            ws_logger.info(
                "[DATA] Telemetría validada: CPU=%s%% RAM=%s%%",
                model.cpu,
                model.ram,
            )
            alert = analyzer.analyze(model)
            ack = TelemetryAck(status="ok", cpu_received=model.cpu)
            await websocket.send_text(ack.model_dump_json())
            if alert is not None:
                now = time.time()
                if (now - last_ai_alert_time) > AI_COOLDOWN_SECONDS:
                    advice = groq_client.get_telemetry_advice(model.cpu, model.ram)
                    last_ai_alert_time = time.time()
                    await websocket.send_json(
                        {"type": "alert", "level": "warning", "message": advice}
                    )
                    try:
                        asyncio.create_task(tts_manager.speak(advice))
                    except Exception as exc:
                        ws_logger.warning("No se pudo iniciar TTS: %s", exc)
                else:
                    ws_logger.info("Alerta activa, pero Groq en cooldown.")
                    await websocket.send_json(
                        {"type": "alert", "level": "warning", "message": ""}
                    )
    except WebSocketDisconnect:
        ws_logger.info("WebSocket disconnected")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=True)
