"""Esquemas Pydantic (contratos de datos Rust <-> Python <-> UI)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _coerce_json_number(v: Any) -> float:
    # `serde_json` puede emitir enteros para valores enteros; strict=True no coacciona int→float.
    if isinstance(v, bool):
        raise ValueError("boolean is not a valid numeric telemetry value")
    if isinstance(v, int | float):
        return float(v)
    raise ValueError("expected int or float")


class ProcessStat(BaseModel):
    """Proceso agregado por nombre, tal como lo envía Rust."""

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str
    cpu: float
    mem_mb: float

    @field_validator("cpu", "mem_mb", mode="before")
    @classmethod
    def coerce_json_number_to_float(cls, v: Any) -> float:
        return _coerce_json_number(v)


class SystemTelemetry(BaseModel):
    """Contrato del JSON de telemetría enviado por Rust.

    `top` es opcional (default vacío) para tolerar emisores antiguos.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    cpu: float
    ram: float
    top: list[ProcessStat] = Field(default_factory=list)

    @field_validator("cpu", "ram", mode="before")
    @classmethod
    def coerce_json_number_to_float(cls, v: Any) -> float:
        return _coerce_json_number(v)


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


class Intent(BaseModel):
    """Intención estructurada extraída del texto del usuario por el LLM.

    `tool="chat"` es el default: conversación libre (streaming). Cualquier
    otro valor se busca en el registro del ToolDispatcher.
    """

    model_config = ConfigDict(extra="forbid")

    tool: str = "chat"
    args: dict[str, Any] = Field(default_factory=dict)


class VoiceStateEvent(BaseModel):
    """Estado del pipeline de voz. Rust lo reenvía a la UI como `voice-state`."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["voice"] = "voice"
    state: Literal["listening", "transcribing", "thinking", "speaking", "idle", "error"]
    detail: Optional[str] = None
