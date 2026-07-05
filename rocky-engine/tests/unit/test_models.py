import pytest
from pydantic import ValidationError

from src.domain.models import AlertEvent, ChatEvent, SystemTelemetry, VoiceStateEvent


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

    def test_rejects_booleans(self) -> None:
        with pytest.raises(ValidationError):
            SystemTelemetry.model_validate({"cpu": True, "ram": 40.0})

    def test_rejects_strings(self) -> None:
        with pytest.raises(ValidationError):
            SystemTelemetry.model_validate({"cpu": "12.5", "ram": 40.0})

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            SystemTelemetry.model_validate({"cpu": 1.0, "ram": 2.0, "gpu": 3.0})

    def test_top_defaults_to_empty(self) -> None:
        # Compatibilidad con emisores antiguos que no envían procesos.
        assert SystemTelemetry.model_validate({"cpu": 1.0, "ram": 2.0}).top == []

    def test_parses_top_processes_with_int_coercion(self) -> None:
        t = SystemTelemetry.model_validate(
            {
                "cpu": 10.0,
                "ram": 20.0,
                "top": [{"name": "chrome", "cpu": 40, "mem_mb": 2048}],
            }
        )
        assert t.top[0].name == "chrome"
        assert t.top[0].cpu == 40.0
        assert isinstance(t.top[0].mem_mb, float)

    def test_top_process_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            SystemTelemetry.model_validate(
                {
                    "cpu": 1.0,
                    "ram": 2.0,
                    "top": [{"name": "x", "cpu": 1, "mem_mb": 1, "pid": 42}],
                }
            )


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
