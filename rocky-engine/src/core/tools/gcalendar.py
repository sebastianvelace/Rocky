"""Herramienta de Google Calendar."""

from __future__ import annotations

import asyncio
from typing import Any

from src.domain.interfaces import BaseTool
from src.infrastructure.clients.gcalendar_client import NOT_CONFIGURED, GCalendarClient


class CalendarTodayTool(BaseTool):
    name = "calendar.today"
    description = (
        "calendar.today: el usuario pregunta qué tiene hoy en la agenda, "
        "sus eventos, reuniones o calendario del día."
    )

    def __init__(self, client: GCalendarClient) -> None:
        self._client = client

    async def run(
        self, args: dict[str, Any], telemetry: tuple[float, float] | None
    ) -> str:
        if not self._client.available:
            return NOT_CONFIGURED

        events = await asyncio.to_thread(self._client.events_today)
        if events is None:
            return "No pude leer el calendario. Reintenta en un momento."
        if not events:
            return "Hoy no tienes nada en la agenda. Día limpio, Sebas."

        lines = [f"• {e['start']} — {e['summary']}" for e in events]
        plural = "evento" if len(events) == 1 else "eventos"
        return f"Hoy tienes {len(events)} {plural}:\n" + "\n".join(lines)
