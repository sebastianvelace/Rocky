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
        heuristic = self._safe_local_intent(user_text)
        if heuristic is not None:
            return heuristic
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

    @staticmethod
    def _safe_local_intent(user_text: str) -> Intent | None:
        """Las dos capacidades de investigación siguen disponibles sin LLM.

        Son acciones solo de lectura y con una señal lingüística explícita; no
        convierten una conversación normal en una búsqueda inesperada.
        """
        text = user_text.strip()
        normalized = text.casefold()
        if any(marker in normalized for marker in ("busca en internet", "investiga en la web", "busca en la web", "web search")):
            return Intent(tool="web.search", args={"query": text})
        if any(marker in normalized for marker in ("busca en mis archivos", "busca en el repositorio", "busca localmente", "search workspace")):
            return Intent(tool="workspace.search", args={"query": text})
        return None
