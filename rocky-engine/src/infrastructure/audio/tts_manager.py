from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from typing import Final


class TTSManager:
    _VOICES: Final[tuple[str, ...]] = ("es-MX-JorgeNeural", "es-ES-AlvaroNeural")

    def __init__(self, voice: str | None = None, player_cmd: str = "mpv") -> None:
        self._voice = voice or self._VOICES[0]
        self._player_cmd = player_cmd
        self._logger = logging.getLogger("rocky.tts")

    async def speak(self, text: str) -> None:
        if not text or not text.strip():
            return

        try:
            import edge_tts  # type: ignore

            voice = self._voice if self._voice in self._VOICES else self._VOICES[0]
            with tempfile.NamedTemporaryFile(prefix="rocky_tts_", suffix=".mp3", delete=False) as f:
                out_path = f.name

            try:
                communicate = edge_tts.Communicate(text=text.strip(), voice=voice)
                await communicate.save(out_path)

                proc = await asyncio.create_subprocess_exec(
                    self._player_cmd,
                    "--no-video",
                    out_path,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.communicate()
            finally:
                try:
                    os.unlink(out_path)
                except Exception:
                    pass
        except Exception as exc:
            # Resiliencia: el backend debe seguir funcionando aunque el audio falle.
            self._logger.warning("TTS no disponible: %s", exc)
