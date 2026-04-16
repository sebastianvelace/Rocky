"""Esquemas Pydantic (validación de datos)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class SystemTelemetry(BaseModel):
    """Contrato del JSON de telemetría enviado por Rust (`{cpu, ram}`)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    cpu: float
    ram: float

    @field_validator("cpu", "ram", mode="before")
    @classmethod
    def coerce_json_number_to_float(cls, v: Any) -> float:
        # `serde_json` puede emitir enteros para valores enteros; strict=True no coacciona int→float.
        if isinstance(v, bool):
            raise ValueError("boolean is not a valid numeric telemetry value")
        if isinstance(v, int | float):
            return float(v)
        raise ValueError("expected int or float")


class TelemetryAck(BaseModel):
    """Confirmación estructurada hacia el cliente WebSocket (Rust)."""

    model_config = ConfigDict(extra="forbid")

    status: str = "ok"
    cpu_received: float
