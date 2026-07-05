"""Cliente de Spotify (spotipy) con degradación sin credenciales.

OAuth de usuario: la primera vez abre el navegador para autorizar y cachea
el token en el directorio de datos de Rocky. Sin SPOTIFY_CLIENT_ID/SECRET
el cliente queda inactivo y las herramientas responden cómo configurarlo.
"""

from __future__ import annotations

import logging
import os

from src.infrastructure.history_store import default_db_path

_SCOPES = "user-modify-playback-state user-read-playback-state"
_NOT_CONFIGURED = (
    "Spotify no está configurado: define SPOTIFY_CLIENT_ID y "
    "SPOTIFY_CLIENT_SECRET en el .env (dashboard de Spotify Developers)."
)
_NO_DEVICE = (
    "No hay ningún dispositivo de Spotify activo. Abre Spotify en algún "
    "aparato y vuelve a pedírmelo."
)


class SpotifyClient:
    def __init__(self) -> None:
        self._logger = logging.getLogger("rocky.spotify")
        self._sp = None

        client_id = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
        redirect_uri = os.getenv(
            "SPOTIFY_REDIRECT_URI", "http://localhost:8000/callback"
        ).strip()

        if not client_id or not client_secret:
            self._logger.warning("Spotify sin credenciales: herramientas inactivas")
            return

        try:
            import spotipy  # type: ignore
            from spotipy.cache_handler import CacheFileHandler  # type: ignore
            from spotipy.oauth2 import SpotifyOAuth  # type: ignore

            cache_path = default_db_path().parent / "spotify_token.json"
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._sp = spotipy.Spotify(
                auth_manager=SpotifyOAuth(
                    client_id=client_id,
                    client_secret=client_secret,
                    redirect_uri=redirect_uri,
                    scope=_SCOPES,
                    cache_handler=CacheFileHandler(cache_path=str(cache_path)),
                )
            )
        except Exception as exc:
            self._logger.warning("Spotify no disponible: %s", exc)
            self._sp = None

    # Todos los métodos son bloqueantes (correr en hilo) y devuelven el
    # mensaje humano que Rocky dirá: la herramienta no formatea, solo ejecuta.

    def play(self, query: str | None = None) -> str:
        if self._sp is None:
            return _NOT_CONFIGURED
        try:
            if query:
                results = self._sp.search(q=query, type="track", limit=1)
                items = results.get("tracks", {}).get("items", [])
                if not items:
                    return f"No encontré nada para «{query}» en Spotify."
                track = items[0]
                self._sp.start_playback(uris=[track["uri"]])
                artist = track["artists"][0]["name"] if track.get("artists") else "?"
                return f"Sonando: {track['name']} — {artist}."
            self._sp.start_playback()
            return "Reanudando la música."
        except Exception as exc:
            return self._playback_error(exc)

    def pause(self) -> str:
        if self._sp is None:
            return _NOT_CONFIGURED
        try:
            self._sp.pause_playback()
            return "Música pausada."
        except Exception as exc:
            return self._playback_error(exc)

    def next_track(self) -> str:
        if self._sp is None:
            return _NOT_CONFIGURED
        try:
            self._sp.next_track()
            return "Saltando a la siguiente."
        except Exception as exc:
            return self._playback_error(exc)

    def _playback_error(self, exc: Exception) -> str:
        message = str(exc)
        self._logger.warning("Spotify falló: %s", message)
        if "NO_ACTIVE_DEVICE" in message or "Device not found" in message:
            return _NO_DEVICE
        return "Spotify no respondió. Reintenta en un momento."
