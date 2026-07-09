"""Investigación web acotada y legible para el modelo."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.domain.interfaces import BaseTool
from src.domain.models import SystemTelemetry


class WebResearchTool(BaseTool):
    name = "web.search"
    capability = "web.research"
    description = "web.search: investiga información actual en Internet, busca fuentes web o noticias. args: {query}."

    async def run(self, args: dict[str, Any], telemetry: SystemTelemetry | None) -> str:
        # Defensa en profundidad para llamadas directas fuera del dispatcher.
        if os.getenv("ROCKY_WEB_ENABLED", "true").strip().lower() not in {"1", "true", "yes"}:
            return "La investigación web está desactivada por configuración."
        query = str(args.get("query", "")).strip()
        if len(query) < 2:
            return "Indica una consulta para investigar en la web."
        url = "https://api.duckduckgo.com/?" + urlencode({"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"})
        try:
            request = Request(url, headers={"User-Agent": "Rocky/0.2 research"})
            with urlopen(request, timeout=8) as response:
                payload = json.load(response)
        except Exception as exc:
            return f"No pude consultar la web: {exc}"

        findings: list[str] = []
        abstract = str(payload.get("AbstractText", "")).strip()
        abstract_url = str(payload.get("AbstractURL", "")).strip()
        if abstract:
            findings.append(f"{abstract} {abstract_url}".strip())
        for item in payload.get("RelatedTopics", []):
            if not isinstance(item, dict):
                continue
            text, source = str(item.get("Text", "")).strip(), str(item.get("FirstURL", "")).strip()
            if text:
                findings.append(f"{text} {source}".strip())
            if len(findings) >= 4:
                break
        return "Fuentes web:\n" + "\n".join(f"- {item}" for item in findings) if findings else "La búsqueda no devolvió una fuente resumible; reformula la consulta."
