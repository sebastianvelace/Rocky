"""Entry point de rocky-engine: composición de dependencias y FastAPI."""

from __future__ import annotations

# Carga opcional de variables desde .env (si existe y está instalado python-dotenv).
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(override=False)
except Exception:
    pass

from fastapi import FastAPI

from src.api.middleware import RockySecurity
from src.api.websocket import create_ws_router
from src.core.analyzer import SystemAnalyzer
from src.infrastructure.audio.stt_manager import STTManager
from src.infrastructure.audio.tts_manager import TTSManager
from src.infrastructure.clients.groq_client import GroqClient
from src.infrastructure.logger import configure_logging
from src.orchestrator import RockyOrchestrator

configure_logging()

app = FastAPI(title="Rocky Engine")

orchestrator = RockyOrchestrator(
    analyzer=SystemAnalyzer(),
    groq_client=GroqClient(),
    tts_manager=TTSManager(),
    stt_manager=STTManager(),
)
app.include_router(create_ws_router(RockySecurity(), orchestrator))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=True)
