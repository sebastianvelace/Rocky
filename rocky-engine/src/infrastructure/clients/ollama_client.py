"""Cliente mínimo de Ollama para modelos locales y streaming NDJSON.

No usa el SDK: la API local de Ollama es HTTP y mantener esta dependencia fuera
del engine reduce la RAM y el tiempo de arranque. El host queda limitado a
loopback para que la selección de un modelo no convierta Rocky en un proxy.
"""

from __future__ import annotations

import json
import logging
import os
from collections import deque
from typing import Any, Iterator
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.domain.models import SystemTelemetry
from src.infrastructure.history_store import HistoryStore


class OllamaClient:
    _FALLBACK = "Ollama local no está disponible. Inicia el servicio o selecciona otro modelo."
    _HISTORY_MAX_MESSAGES = 12

    def __init__(self, history_store: HistoryStore | None = None) -> None:
        self._logger = logging.getLogger("rocky.ollama")
        self._base_url = self._validated_base_url(
            os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        )
        self._timeout = float(os.getenv("ROCKY_OLLAMA_TIMEOUT_SECONDS", "45"))
        self._model = os.getenv("ROCKY_OLLAMA_MODEL", "").strip() or None
        self._store = history_store
        self._history: deque[dict[str, str]] = deque(maxlen=self._HISTORY_MAX_MESSAGES)
        if history_store is not None:
            self._history.extend(history_store.load_recent(self._HISTORY_MAX_MESSAGES))

    @staticmethod
    def _validated_base_url(raw: str) -> str:
        parsed = urlparse(raw.strip())
        if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("OLLAMA_HOST debe apuntar a http://localhost o 127.0.0.1")
        return raw.rstrip("/")

    @property
    def fallback_text(self) -> str:
        return self._FALLBACK

    @property
    def active_model(self) -> str | None:
        return self._model

    def list_models(self) -> list[dict[str, Any]]:
        """Lista los modelos instalados sin cargar ninguno en memoria."""
        try:
            with urlopen(f"{self._base_url}/api/tags", timeout=self._timeout) as response:
                payload = json.load(response)
            models = payload.get("models", []) if isinstance(payload, dict) else []
            return [model for model in models if isinstance(model, dict) and isinstance(model.get("name"), str)]
        except Exception as exc:
            self._logger.info("Ollama no disponible: %s", exc)
            return []

    def select_model(self, model: str) -> bool:
        selected = model.strip()
        if not selected:
            return False
        if selected not in {entry["name"] for entry in self.list_models()}:
            return False
        self._model = selected
        return True

    def _request(self, payload: dict[str, Any], *, stream: bool) -> Any:
        if not self._model:
            raise RuntimeError("No hay un modelo Ollama seleccionado")
        body = json.dumps({"model": self._model, **payload, "stream": stream}).encode("utf-8")
        request = Request(
            f"{self._base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return urlopen(request, timeout=self._timeout)

    @staticmethod
    def _content(payload: Any) -> str:
        if not isinstance(payload, dict):
            return ""
        message = payload.get("message")
        return message.get("content", "") if isinstance(message, dict) else ""

    def _system_prompt(self, telemetry: SystemTelemetry | None) -> str:
        prompt = (
            "Eres Rocky, un asistente de ingeniería. Responde en español, directo y "
            "conciso. No afirmes haber ejecutado herramientas que no aparecen en el contexto."
        )
        if telemetry is not None:
            prompt += f" Telemetría actual: CPU {telemetry.cpu:.0f}%, RAM {telemetry.ram:.0f}%."
        return prompt

    def _messages(self, prompt: str, telemetry: SystemTelemetry | None) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": self._system_prompt(telemetry)},
            *self._history,
            {"role": "user", "content": prompt},
        ]

    def _remember_turn(self, prompt: str, reply: str) -> None:
        if not reply:
            return
        self._history.extend(({"role": "user", "content": prompt}, {"role": "assistant", "content": reply}))
        if self._store is not None:
            self._store.append("user", prompt)
            self._store.append("assistant", reply)

    def get_intent_json(self, user_text: str, tools_prompt: str) -> str | None:
        if not self._model or not user_text.strip():
            return None
        messages = [
            {
                "role": "system",
                "content": (
                    "Clasifica el mensaje en UNA herramienta. Responde solo JSON con "
                    '{"tool":"nombre","args":{}}. Herramientas:\n'
                    f"{tools_prompt}\nSi no aplica, usa chat."
                ),
            },
            {"role": "user", "content": user_text.strip()},
        ]
        try:
            with self._request({"messages": messages, "format": "json", "options": {"temperature": 0}}, stream=False) as response:
                return self._content(json.load(response)).strip() or None
        except Exception as exc:
            self._logger.warning("Clasificación Ollama falló: %s", exc)
            return None

    def get_telemetry_advice(self, cpu: float, ram: float, resource: str = "cpu") -> str:
        if not self._model:
            return self._FALLBACK
        try:
            with self._request(
                {"messages": [{"role": "system", "content": "Da un consejo de máximo 15 palabras en español."}, {"role": "user", "content": f"Alerta {resource}: CPU {cpu:.1f}%, RAM {ram:.1f}%."}], "options": {"temperature": 0.2}},
                stream=False,
            ) as response:
                return self._content(json.load(response)).strip() or self._FALLBACK
        except Exception as exc:
            self._logger.warning("Alerta Ollama falló: %s", exc)
            return self._FALLBACK

    def stream_conversational_reply(self, user_text: str, telemetry: SystemTelemetry | None = None) -> Iterator[str]:
        prompt = user_text.strip()
        if not self._model or not prompt:
            yield self._FALLBACK
            return
        parts: list[str] = []
        try:
            with self._request({"messages": self._messages(prompt, telemetry), "options": {"temperature": 0.5}}, stream=True) as response:
                for raw_line in response:
                    try:
                        delta = self._content(json.loads(raw_line))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        continue
                    if delta:
                        parts.append(delta)
                        yield delta
        except Exception as exc:
            self._logger.warning("Streaming Ollama falló: %s", exc)
            if not parts:
                yield self._FALLBACK
        finally:
            self._remember_turn(prompt, "".join(parts).strip())
