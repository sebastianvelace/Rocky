"""Herramientas de Spotify. Ejecutan el adaptador; no interpretan lenguaje.

El cliente es bloqueante (spotipy): cada run va en asyncio.to_thread para
no congelar la telemetría.
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.domain.interfaces import BaseTool
from src.domain.models import SystemTelemetry
from src.infrastructure.clients.spotify_client import SpotifyClient


class SpotifyPlayTool(BaseTool):
    name = "spotify.play"
    capability = "spotify.control"
    description = (
        "spotify.play: el usuario pide reproducir música, poner una canción, "
        "artista o playlist, o reanudar la reproducción. args: {\"query\": "
        "\"texto a buscar\"} (omitir query para reanudar)."
    )

    def __init__(self, client: SpotifyClient) -> None:
        self._client = client

    async def run(
        self, args: dict[str, Any], telemetry: SystemTelemetry | None
    ) -> str:
        query = str(args.get("query") or "").strip() or None
        return await asyncio.to_thread(self._client.play, query)


class SpotifyPauseTool(BaseTool):
    name = "spotify.pause"
    capability = "spotify.control"
    description = "spotify.pause: el usuario pide pausar o parar la música."

    def __init__(self, client: SpotifyClient) -> None:
        self._client = client

    async def run(
        self, args: dict[str, Any], telemetry: SystemTelemetry | None
    ) -> str:
        return await asyncio.to_thread(self._client.pause)


class SpotifyNextTool(BaseTool):
    name = "spotify.next"
    capability = "spotify.control"
    description = (
        "spotify.next: el usuario pide saltar a la siguiente canción o "
        "cambiar de tema."
    )

    def __init__(self, client: SpotifyClient) -> None:
        self._client = client

    async def run(
        self, args: dict[str, Any], telemetry: SystemTelemetry | None
    ) -> str:
        return await asyncio.to_thread(self._client.next_track)
