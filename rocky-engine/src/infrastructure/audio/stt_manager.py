from __future__ import annotations

import os
import tempfile
from typing import Final


class STTManager:
    _MODEL: Final[str] = "whisper-large-v3"

    def __init__(self) -> None:
        self._api_key = os.getenv("GROQ_API_KEY")
        self._client = None
        if self._api_key:
            try:
                from groq import Groq  # type: ignore

                self._client = Groq(api_key=self._api_key)
            except Exception:
                self._client = None

    def listen_and_transcribe(self) -> str | None:
        """
        Escucha por micrófono hasta silencio y transcribe usando Groq (Whisper).
        Devuelve texto o None si falla/cancela.
        """
        if not self._client:
            return None

        try:
            import speech_recognition as sr  # type: ignore

            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=1)
                audio = recognizer.listen(source)

            # Exportar a WAV temporal.
            with tempfile.NamedTemporaryFile(prefix="rocky_stt_", suffix=".wav", delete=False) as f:
                wav_path = f.name
                f.write(audio.get_wav_data())

            try:
                with open(wav_path, "rb") as audio_file:
                    transcription = self._client.audio.transcriptions.create(
                        model=self._MODEL,
                        file=audio_file,
                    )

                text = getattr(transcription, "text", None)
                if isinstance(text, str) and text.strip():
                    return text.strip()
                return None
            finally:
                try:
                    os.unlink(wav_path)
                except Exception:
                    pass
        except Exception:
            return None
