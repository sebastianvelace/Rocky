import pytest
from pydantic import ValidationError

from src.domain.models import (
    AlertEvent,
    ChatEvent,
    ProcessTelemetry,
    SystemTelemetry,
    VoiceStateEvent,
)


class TestSystemTelemetry:
    def test_accepts_floats(self) -> None:
        t = SystemTelemetry.model_validate({"cpu": 12.5, "ram": 40.0})
        assert t.cpu == 12.5
        assert t.ram == 40.0

    def test_coerces_json_integers(self) -> None:
        # serde_json (Rust) emite enteros para valores exactos.
        t = SystemTelemetry.model_validate({"cpu": 12, "ram": 40})
        assert t.cpu == 12.0
        assert isinstance(t.cpu, float)

    def test_accepts_process_rankings(self) -> None:
        t = SystemTelemetry.model_validate(
            {
                "cpu": 12,
                "ram": 40,
                "top_cpu": [
                    {
                        "pid": "123",
                        "name": "python",
                        "cpu": 8,
                        "ram": 2,
                        "memory_mb": 256,
                    }
                ],
                "top_ram": [],
            }
        )
        assert t.top_cpu == [
            ProcessTelemetry(
                pid="123", name="python", cpu=8.0, ram=2.0, memory_mb=256.0
            )
        ]

    def test_rejects_booleans(self) -> None:
        with pytest.raises(ValidationError):
            SystemTelemetry.model_validate({"cpu": True, "ram": 40.0})

    def test_rejects_strings(self) -> None:
        with pytest.raises(ValidationError):
            SystemTelemetry.model_validate({"cpu": "12.5", "ram": 40.0})

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            SystemTelemetry.model_validate({"cpu": 1.0, "ram": 2.0, "gpu": 3.0})


class TestOutboundEvents:
    def test_alert_event_serializes_contract(self) -> None:
        event = AlertEvent(resource="ram", message="RAM crítica")
        data = event.model_dump()
        assert data["type"] == "alert"
        assert data["level"] == "warning"
        assert data["resource"] == "ram"

    def test_chat_event_roles(self) -> None:
        assert ChatEvent(role="user", text="hola").type == "chat"
        with pytest.raises(ValidationError):
            ChatEvent(role="bot", text="hola")

    def test_voice_state_values(self) -> None:
        assert VoiceStateEvent(state="listening").detail is None
        with pytest.raises(ValidationError):
            VoiceStateEvent(state="dancing")
