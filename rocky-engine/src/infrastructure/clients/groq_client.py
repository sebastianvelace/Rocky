from __future__ import annotations

import logging
import os
from collections import deque
from typing import Final, Iterator


class GroqClient:
    # Un único modelo válido y vigente para todo el texto. El id anterior
    # ("llama-3-70b-8192") no existe en Groq, por lo que toda alerta caía
    # silenciosamente al mensaje de fallback.
    _CHAT_MODEL: Final[str] = "llama-3.3-70b-versatile"
    _FALLBACK: Final[str] = "Sistema bajo carga, Sebas. Groq está offline."
    # Turnos (user+assistant) que se recuerdan por sesión.
    _HISTORY_MAX_MESSAGES: Final[int] = 12

    def __init__(self) -> None:
        self._logger = logging.getLogger("rocky.groq")
        self._api_key = os.getenv("GROQ_API_KEY")
        self._client = None
        # Memoria conversacional de la sesión: sin ella cada mensaje era un
        # borrón y cuenta nueva y no se podía hilar una conversación.
        self._history: deque[dict[str, str]] = deque(maxlen=self._HISTORY_MAX_MESSAGES)
        if not self._api_key:
            self._logger.warning("GROQ_API_KEY no definido: se usarán respuestas de fallback")
            return

        try:
            from groq import Groq  # type: ignore

            self._client = Groq(api_key=self._api_key)
        except Exception as exc:
            self._logger.warning("Cliente Groq no disponible: %s", exc)
            self._client = None

    def get_telemetry_advice(self, cpu: float, ram: float, resource: str = "cpu") -> str:
        """Consejo corto (máximo 15 palabras) para una alerta de telemetría."""
        if not self._client:
            return self._FALLBACK

        try:
            completion = self._client.chat.completions.create(
                model=self._CHAT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Eres Rocky, un asistente de ingeniería aeroespacial y software. "
                            "Analiza los datos del sistema. Sé directo, profesional y con un toque "
                            "de humor inteligente/sarcástico. El usuario se llama Sebas. "
                            "Máximo 15 palabras."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Alerta sostenida de {resource.upper()}. "
                            f"CPU={cpu:.1f}%, RAM={ram:.1f}%. Consejo accionable en español."
                        ),
                    },
                ],
                temperature=0.6,
                max_tokens=60,
            )
            content = (completion.choices[0].message.content or "").strip()
            if not content:
                return self._FALLBACK
            words = content.split()
            if len(words) > 15:
                return " ".join(words[:15]).rstrip(".,;:!?")
            return content
        except Exception as exc:
            self._logger.warning("Groq (telemetría) falló: %s", exc)
            return self._FALLBACK

    @property
    def fallback_text(self) -> str:
        return self._FALLBACK

    def _build_chat_messages(
        self, prompt: str, telemetry: tuple[float, float] | None
    ) -> list[dict[str, str]]:
        system = (
            "Eres Rocky, un asistente de ingeniería aeroespacial y software. "
            "Sé directo, profesional y con humor inteligente/sarcástico. "
            "Responde en español, conciso (1-2 frases). El usuario se llama Sebas."
        )
        if telemetry is not None:
            cpu, ram = telemetry
            system += (
                f" Telemetría actual del equipo: CPU {cpu:.0f}%, RAM {ram:.0f}%. "
                "Úsala solo si es relevante para la pregunta."
            )
        return [
            {"role": "system", "content": system},
            *self._history,
            {"role": "user", "content": prompt},
        ]

    def _remember_turn(self, prompt: str, reply: str) -> None:
        self._history.append({"role": "user", "content": prompt})
        self._history.append({"role": "assistant", "content": reply})

    def stream_conversational_reply(
        self, user_text: str, telemetry: tuple[float, float] | None = None
    ) -> "Iterator[str]":
        """Respuesta conversacional en streaming (deltas de texto).

        Generador bloqueante (pensado para correr en un hilo). Con memoria de
        sesión y telemetría real en contexto. Si Groq no está disponible,
        emite el fallback como único delta; si el stream muere a mitad, lo ya
        emitido se conserva y se recuerda en el historial.
        """
        prompt = (user_text or "").strip()
        if not self._client or not prompt:
            yield self._FALLBACK
            return

        emitted: list[str] = []
        try:
            stream = self._client.chat.completions.create(
                model=self._CHAT_MODEL,
                messages=self._build_chat_messages(prompt, telemetry),
                temperature=0.7,
                max_tokens=140,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    emitted.append(delta)
                    yield delta
        except Exception as exc:
            self._logger.warning("Groq (chat stream) falló: %s", exc)
            if not emitted:
                yield self._FALLBACK
                return
        finally:
            full = "".join(emitted).strip()
            if full:
                self._remember_turn(prompt, full)

    def get_conversational_reply(
        self, user_text: str, telemetry: tuple[float, float] | None = None
    ) -> str:
        """Versión no-streaming: acumula el stream y devuelve el texto completo."""
        parts = list(self.stream_conversational_reply(user_text, telemetry))
        return "".join(parts).strip() or self._FALLBACK
