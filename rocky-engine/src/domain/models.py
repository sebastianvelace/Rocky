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


class ProcessTelemetry(BaseModel):
    """Proceso observado por Rust/sysinfo en los rankings de consumo."""

    model_config = ConfigDict(strict=True, extra="forbid")

    pid: str
    name: str
    cpu: float
    ram: float
    memory_mb: float
    protected: bool = False
    protection_reason: str | None = None

    @field_validator("cpu", "ram", "memory_mb", mode="before")
    @classmethod
    def coerce_json_number_to_float(cls, v: Any) -> float:
        return _coerce_json_number(v)


class SystemTelemetry(BaseModel):
    """Contrato del JSON de telemetría enviado por Rust.

    Los rankings son opcionales (default vacío) para tolerar emisores antiguos.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    cpu: float
    ram: float
    disk_used: float = 0.0
    network_rx_kbps: float = 0.0
    network_tx_kbps: float = 0.0
    temperature_c: float | None = None
    top_cpu: list[ProcessTelemetry] = Field(default_factory=list)
    top_ram: list[ProcessTelemetry] = Field(default_factory=list)

    @field_validator("cpu", "ram", "disk_used", "network_rx_kbps", "network_tx_kbps", mode="before")
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


class ModelOption(BaseModel):
    """Modelo local expuesto por Ollama, sin revelar detalles del host."""

    model_config = ConfigDict(extra="forbid")

    id: str
    size_bytes: int | None = None
    parameter_size: str | None = None
    quantization: str | None = None
    loaded: bool = False
    memory_bytes: int | None = None
    context_length: int | None = None


class ModelStatusEvent(BaseModel):
    """Estado de los modelos disponibles para el selector de la UI."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["model-status"] = "model-status"
    provider: Literal["ollama", "groq", "none"] = "none"
    active_model: str | None = None
    models: list[ModelOption] = Field(default_factory=list)
    detail: str | None = None


class ToolActivityEvent(BaseModel):
    """Evento auditable de herramienta, sin exponer argumentos sensibles."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["tool-activity"] = "tool-activity"
    tool: str
    capability: str
    status: Literal["completed", "denied", "failed"]
    duration_ms: int = 0
    detail: str | None = None
