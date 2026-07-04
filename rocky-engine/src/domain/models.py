"""Esquemas Pydantic (contratos de datos Rust <-> Python <-> UI)."""

from __future__ import annotations

from typing import Any, Literal, Optional

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


class AlertEvent(BaseModel):
    """Alerta proactiva de telemetría. Rust la reenvía a la UI como `system-alert`."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["alert"] = "alert"
    level: Literal["info", "warning", "critical"] = "warning"
    resource: Literal["cpu", "ram"]
    message: str


class ChatEvent(BaseModel):
    """Turno de conversación (transcripción del usuario o respuesta de Rocky).

    Rust lo reenvía a la UI como `rocky-chat`. Con `partial=True` el texto es
    un delta de streaming que la UI anexa al mensaje en curso; el evento final
    (`partial=False`) trae el texto completo y cierra el mensaje.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["chat"] = "chat"
    role: Literal["user", "rocky"]
    text: str
    partial: bool = False


class VoiceStateEvent(BaseModel):
    """Estado del pipeline de voz. Rust lo reenvía a la UI como `voice-state`."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["voice"] = "voice"
    state: Literal["listening", "transcribing", "thinking", "speaking", "idle", "error"]
    detail: Optional[str] = None
