"""Análisis reactivo de telemetría (umbrales sostenidos)."""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.models import SystemTelemetry

CPU_THRESHOLD = 80.0
RAM_THRESHOLD = 90.0
SUSTAINED_TICKS = 3


@dataclass(frozen=True)
class ThresholdAlert:
    """Umbral superado de forma sostenida. `resource` es "cpu" o "ram"."""

    resource: str
    value: float


class SystemAnalyzer:
    """Detecta patrones sostenidos (CPU/RAM altas varios ticks seguidos).

    Un pico aislado no dispara nada: el umbral debe superarse durante
    ``SUSTAINED_TICKS`` lecturas consecutivas (1 tick ≈ 1 s desde Rust).
    """

    def __init__(
        self,
        cpu_threshold: float = CPU_THRESHOLD,
        ram_threshold: float = RAM_THRESHOLD,
        sustained_ticks: int = SUSTAINED_TICKS,
    ) -> None:
        self.cpu_threshold = cpu_threshold
        self.ram_threshold = ram_threshold
        self.sustained_ticks = sustained_ticks
        self._high_cpu_count = 0
        self._high_ram_count = 0

    def analyze(self, telemetry: SystemTelemetry) -> ThresholdAlert | None:
        cpu_alert = self._check(telemetry.cpu, self.cpu_threshold, "_high_cpu_count", "cpu")
        ram_alert = self._check(telemetry.ram, self.ram_threshold, "_high_ram_count", "ram")
        # La RAM tiene prioridad: quedarse sin memoria es más grave que CPU alta.
        return ram_alert or cpu_alert

    def _check(
        self, value: float, threshold: float, counter_attr: str, resource: str
    ) -> ThresholdAlert | None:
        if value > threshold:
            count = getattr(self, counter_attr) + 1
            if count >= self.sustained_ticks:
                setattr(self, counter_attr, 0)
                return ThresholdAlert(resource=resource, value=value)
            setattr(self, counter_attr, count)
        else:
            setattr(self, counter_attr, 0)
        return None
