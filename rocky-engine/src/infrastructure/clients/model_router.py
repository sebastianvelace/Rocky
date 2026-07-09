"""Proveedor de IA seleccionable sin exponer endpoints al frontend."""

from __future__ import annotations

import os
from typing import Any, Iterator

from src.domain.models import SystemTelemetry
from src.infrastructure.clients.groq_client import GroqClient
from src.infrastructure.clients.ollama_client import OllamaClient
from src.infrastructure.history_store import HistoryStore


class ModelRouter:
    def __init__(self, history_store: HistoryStore) -> None:
        self._groq = GroqClient(history_store=history_store)
        self._ollama = OllamaClient(history_store=history_store)
        preferred = os.getenv("ROCKY_MODEL_PROVIDER", "groq").strip().lower()
        self._provider = "ollama" if preferred == "ollama" and self._ollama.active_model else "groq"

    @property
    def fallback_text(self) -> str:
        return self._active.fallback_text

    @property
    def _active(self) -> GroqClient | OllamaClient:
        return self._ollama if self._provider == "ollama" else self._groq

    def get_intent_json(self, user_text: str, tools_prompt: str) -> str | None:
        return self._active.get_intent_json(user_text, tools_prompt)

    def get_telemetry_advice(self, cpu: float, ram: float, resource: str = "cpu") -> str:
        return self._active.get_telemetry_advice(cpu, ram, resource)

    def stream_conversational_reply(self, user_text: str, telemetry: SystemTelemetry | None = None) -> Iterator[str]:
        return self._active.stream_conversational_reply(user_text, telemetry)

    def status(self) -> dict[str, Any]:
        models = self._ollama.list_models()
        running = {entry["name"]: entry for entry in self._ollama.list_running_models()}
        provider = self._provider
        detail: str | None = None
        if provider == "ollama" and not models:
            provider = "none"
            detail = "Ollama no está disponible o no tiene modelos instalados."
        elif provider == "groq" and not self._groq.available:
            provider = "none"
            detail = "Groq no está configurado; selecciona un modelo local de Ollama."
        return {
            "provider": provider,
            "active_model": (
                self._ollama.active_model if self._provider == "ollama" else "llama-3.3-70b-versatile (Groq)"
            ) if provider != "none" else None,
            "models": [
                {
                    "id": entry["name"],
                    "size_bytes": entry.get("size"),
                    "parameter_size": entry.get("details", {}).get("parameter_size") if isinstance(entry.get("details"), dict) else None,
                    "quantization": entry.get("details", {}).get("quantization_level") if isinstance(entry.get("details"), dict) else None,
                    "loaded": entry["name"] in running,
                    "memory_bytes": running.get(entry["name"], {}).get("size_vram") or running.get(entry["name"], {}).get("size"),
                    "context_length": running.get(entry["name"], {}).get("context_length"),
                }
                for entry in models
            ],
            "detail": detail if detail is not None else (None if models else "Ollama no está disponible o no tiene modelos instalados."),
        }

    def select_ollama_model(self, model: str) -> bool:
        if not self._ollama.select_model(model):
            return False
        self._provider = "ollama"
        return True
