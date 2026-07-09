import pytest
from pydantic import ValidationError

from src.domain.models import (
    AlertEvent,
    ChatEvent,
    ModelStatusEvent,
    ToolActivityEvent,
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
                        "protected": True,
                        "protection_reason": "proceso interno de Rocky",
                    }
                ],
                "top_ram": [],
            }
        )
        assert t.top_cpu == [
            ProcessTelemetry(
                pid="123",
                name="python",
                cpu=8.0,
                ram=2.0,
                memory_mb=256.0,
                protected=True,
                protection_reason="proceso interno de Rocky",
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

    def test_process_rankings_default_to_empty(self) -> None:
        # Compatibilidad con emisores antiguos que no envían procesos.
        t = SystemTelemetry.model_validate({"cpu": 1.0, "ram": 2.0})
        assert t.top_cpu == []
        assert t.top_ram == []

    def test_parses_process_rankings_with_int_coercion(self) -> None:
        t = SystemTelemetry.model_validate(
            {
                "cpu": 10.0,
                "ram": 20.0,
                "top_cpu": [
                    {
                        "pid": "123",
                        "name": "chrome",
                        "cpu": 40,
                        "ram": 3,
                        "memory_mb": 2048,
                    }
                ],
            }
        )
        assert t.top_cpu[0].name == "chrome"
        assert t.top_cpu[0].cpu == 40.0
        assert isinstance(t.top_cpu[0].memory_mb, float)

    def test_process_ranking_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            SystemTelemetry.model_validate(
                {
                    "cpu": 1.0,
                    "ram": 2.0,
                    "top_cpu": [
                        {
                            "pid": "42",
                            "name": "x",
                            "cpu": 1,
                            "ram": 1,
                            "memory_mb": 1,
                            "mem_mb": 1,
                        }
                    ],
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

    def test_model_status_serializes_local_models(self) -> None:
        event = ModelStatusEvent(
            provider="ollama",
            active_model="qwen3:8b",
            models=[{"id": "qwen3:8b", "size_bytes": 5_000_000_000}],
        )
        assert event.type == "model-status"
        assert event.models[0].id == "qwen3:8b"

    def test_tool_activity_never_contains_arguments(self) -> None:
        event = ToolActivityEvent(
            tool="web.search",
            capability="web.research",
            status="completed",
            duration_ms=12,
        )
        assert event.model_dump() == {
            "type": "tool-activity",
            "tool": "web.search",
            "capability": "web.research",
            "status": "completed",
            "duration_ms": 12,
            "detail": None,
        }
