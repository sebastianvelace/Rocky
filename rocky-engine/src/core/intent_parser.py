"""Intent parser: texto libre → Intent (Pydantic) validado.

Regla del blueprint: este módulo SOLO convierte texto a un schema; no ejecuta
nada. Cualquier error (sin API key, JSON malformado, herramienta desconocida
para el schema) degrada a `Intent(tool="chat")` — la conversación nunca se
rompe por culpa del clasificador.
"""

from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from src.domain.models import Intent
from src.infrastructure.clients.groq_client import GroqClient


class IntentParser:
    def __init__(self, groq_client: GroqClient, tools_prompt: str) -> None:
        self._groq = groq_client
        self._tools_prompt = tools_prompt
        self._logger = logging.getLogger("rocky.intent")

    def parse(self, user_text: str) -> Intent:
        """Bloqueante (correr en hilo). Nunca lanza: degrada a chat."""
        raw = self._groq.get_intent_json(user_text, self._tools_prompt)
        if not raw:
            return Intent()

        try:
            data = json.loads(raw)
            intent = Intent.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            self._logger.warning("Intent inválido (%s); degradando a chat", exc)
            return Intent()

        self._logger.info("Intent: %s", intent.tool)
        return intent
