"""Cliente de Google Calendar con degradación sin credenciales.

Soporta dos tipos de JSON en GOOGLE_APPLICATION_CREDENTIALS:
- Service account («type»: «service_account»): acceso directo (el calendario
  debe estar compartido con la cuenta de servicio).
- OAuth de usuario (client secrets): la primera vez abre el navegador y
  cachea el token en el directorio de datos de Rocky.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
from pathlib import Path
from typing import Any

from src.infrastructure.history_store import default_db_path

_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
NOT_CONFIGURED = (
    "Google Calendar no está configurado: apunta "
    "GOOGLE_APPLICATION_CREDENTIALS a tu JSON de credenciales en el .env."
)


class GCalendarClient:
    def __init__(self) -> None:
        self._logger = logging.getLogger("rocky.gcalendar")
        self._service: Any = None

        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        if not creds_path:
            self._logger.warning("Calendar sin credenciales: herramienta inactiva")
            return

        try:
            self._service = self._build_service(Path(creds_path))
        except Exception as exc:
            self._logger.warning("Calendar no disponible: %s", exc)
            self._service = None

    def _build_service(self, creds_path: Path) -> Any:
        from googleapiclient.discovery import build  # type: ignore

        info = json.loads(creds_path.read_text())
        if info.get("type") == "service_account":
            from google.oauth2 import service_account  # type: ignore

            creds = service_account.Credentials.from_service_account_file(
                str(creds_path), scopes=_SCOPES
            )
        else:
            creds = self._user_oauth(creds_path)
        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    def _user_oauth(self, client_secrets: Path) -> Any:
        from google.auth.transport.requests import Request  # type: ignore
        from google.oauth2.credentials import Credentials  # type: ignore
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore

        token_path = default_db_path().parent / "gcalendar_token.json"
        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), _SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), _SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())
        return creds

    @property
    def available(self) -> bool:
        return self._service is not None

    def events_today(self) -> list[dict[str, str]] | None:
        """Eventos de hoy `[{start, summary}]` (hora local), o None si falla.
        Bloqueante: correr en hilo."""
        if self._service is None:
            return None

        try:
            now = dt.datetime.now().astimezone()
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + dt.timedelta(days=1)
            result = (
                self._service.events()
                .list(
                    calendarId="primary",
                    timeMin=start.isoformat(),
                    timeMax=end.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=20,
                )
                .execute()
            )
            events = []
            for item in result.get("items", []):
                raw_start = item.get("start", {})
                when = raw_start.get("dateTime") or raw_start.get("date") or ""
                if "T" in when:
                    when = when.split("T", 1)[1][:5]  # HH:MM
                else:
                    when = "todo el día"
                events.append({"start": when, "summary": item.get("summary", "(sin título)")})
            return events
        except Exception as exc:
            self._logger.warning("Calendar falló: %s", exc)
            return None
