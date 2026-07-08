"""Tests de las herramientas de Spotify y Calendar (con fakes, sin red)."""

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from src.core.tools.gcalendar import CalendarTodayTool
from src.core.tools.spotify import SpotifyNextTool, SpotifyPauseTool, SpotifyPlayTool
from src.infrastructure.clients.gcalendar_client import GCalendarClient
from src.infrastructure.clients.spotify_client import SpotifyClient


@pytest.fixture(autouse=True)
def isolated_tool_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    async def inline_to_thread(func: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", inline_to_thread)
    for key in (
        "SPOTIFY_CLIENT_ID",
        "SPOTIFY_CLIENT_SECRET",
        "SPOTIFY_REDIRECT_URI",
        "GOOGLE_APPLICATION_CREDENTIALS",
    ):
        monkeypatch.delenv(key, raising=False)


class FakeSpotify:
    """Sin credenciales en el entorno de test: registra las llamadas."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def play(self, query: str | None = None) -> str:
        self.calls.append(("play", query))
        return f"play:{query}"

    def pause(self) -> str:
        self.calls.append(("pause", None))
        return "pause"

    def next_track(self) -> str:
        self.calls.append(("next", None))
        return "next"


class FakeCalendar:
    def __init__(self, events: list[dict[str, str]] | None) -> None:
        self._events = events
        self._available = True

    @property
    def available(self) -> bool:
        return self._available

    def events_today(self) -> list[dict[str, str]] | None:
        return self._events


class TestSpotifyTools:
    async def test_play_passes_query(self) -> None:
        client = FakeSpotify()
        result = await SpotifyPlayTool(client).run({"query": "queen"}, None)  # type: ignore[arg-type]
        assert result == "play:queen"
        assert client.calls == [("play", "queen")]

    async def test_play_without_query_resumes(self) -> None:
        client = FakeSpotify()
        result = await SpotifyPlayTool(client).run({}, None)  # type: ignore[arg-type]
        assert result == "play:None"

    async def test_pause_and_next(self) -> None:
        client = FakeSpotify()
        assert await SpotifyPauseTool(client).run({}, None) == "pause"  # type: ignore[arg-type]
        assert await SpotifyNextTool(client).run({}, None) == "next"  # type: ignore[arg-type]

    async def test_without_credentials_replies_how_to_configure(self) -> None:
        # SpotifyClient real sin credenciales (entorno de test limpio).
        result = await SpotifyPlayTool(SpotifyClient()).run({"query": "x"}, None)
        assert "SPOTIFY_CLIENT_ID" in result


class TestCalendarTool:
    async def test_formats_events(self) -> None:
        tool = CalendarTodayTool(  # type: ignore[arg-type]
            FakeCalendar(
                [
                    {"start": "09:00", "summary": "Standup"},
                    {"start": "14:30", "summary": "Review"},
                ]
            )
        )
        result = await tool.run({}, None)
        assert "2 eventos" in result
        assert "09:00 — Standup" in result

    async def test_empty_agenda(self) -> None:
        result = await CalendarTodayTool(FakeCalendar([])).run({}, None)  # type: ignore[arg-type]
        assert "nada en la agenda" in result.lower()

    async def test_api_failure_is_friendly(self) -> None:
        result = await CalendarTodayTool(FakeCalendar(None)).run({}, None)  # type: ignore[arg-type]
        assert "no pude leer" in result.lower()

    async def test_without_credentials_replies_how_to_configure(self) -> None:
        result = await CalendarTodayTool(GCalendarClient()).run({}, None)
        assert "GOOGLE_APPLICATION_CREDENTIALS" in result
