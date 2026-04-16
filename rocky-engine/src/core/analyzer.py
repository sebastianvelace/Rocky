"""Análisis reactivo de telemetría (umbrales consecutivos)."""

from __future__ import annotations

from typing import Any

from src.domain.models import SystemTelemetry


class SystemAnalyzer:
    """Detecta patrones sostenidos (p. ej. CPU alta varios segundos seguidos)."""

    def __init__(self) -> None:
        self.high_cpu_count = 0

    def analyze(self, telemetry: SystemTelemetry) -> dict[str, Any] | None:
        if telemetry.cpu > 80.0:
            self.high_cpu_count += 1
            if self.high_cpu_count >= 3:
                self.high_cpu_count = 0
                return {
                    "type": "alert",
                    "level": "warning",
                    "message": "Sobrecarga de CPU detectada",
                }
        else:
            self.high_cpu_count = 0
        return None
