from __future__ import annotations

import os
from typing import Final


class GroqClient:
    _TELEMETRY_MODEL: Final[str] = "llama-3-70b-8192"
    _CHAT_MODEL: Final[str] = "llama-3.3-70b-versatile"
    _FALLBACK: Final[str] = "Sistema bajo carga, Sebas. Groq está offline."

    def __init__(self) -> None:
        self._api_key = os.getenv("GROQ_API_KEY")
        self._client = None
        if not self._api_key:
            return

        try:
            from groq import Groq  # type: ignore

            self._client = Groq(api_key=self._api_key)
        except Exception:
            self._client = None

    def get_telemetry_advice(self, cpu: float, ram: float) -> str:
        """Consejo corto (máximo 15 palabras) para telemetría."""
        if not self._client:
            return self._FALLBACK

        try:
            completion = self._client.chat.completions.create(
                model=self._TELEMETRY_MODEL,
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
                        "content": f"CPU={cpu:.1f}%, RAM={ram:.1f}%. Consejo accionable en español.",
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
        except Exception:
            return self._FALLBACK

    def get_conversational_reply(self, user_text: str) -> str:
        """Respuesta conversacional concisa y sarcástica (Llama 3.3)."""
        if not self._client:
            return self._FALLBACK

        prompt = (user_text or "").strip()
        if not prompt:
            return self._FALLBACK

        try:
            completion = self._client.chat.completions.create(
                model=self._CHAT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Eres Rocky, un asistente de ingeniería aeroespacial y software. "
                            "Sé directo, profesional y con humor inteligente/sarcástico. "
                            "Responde en español, conciso (1-2 frases). El usuario se llama Sebas."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=140,
            )
            content = (completion.choices[0].message.content or "").strip()
            return content if content else self._FALLBACK
        except Exception:
            return self._FALLBACK