import io
import json

from src.infrastructure.clients.ollama_client import OllamaClient


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_list_and_select_installed_ollama_model(monkeypatch) -> None:
    payload = {"models": [{"name": "qwen3:8b", "size": 4, "details": {"parameter_size": "8B"}}]}
    monkeypatch.setattr(
        "src.infrastructure.clients.ollama_client.urlopen",
        lambda *_args, **_kwargs: FakeResponse(json.dumps(payload).encode()),
    )
    client = OllamaClient()

    assert client.list_models()[0]["name"] == "qwen3:8b"
    assert client.select_model("qwen3:8b") is True
    assert client.active_model == "qwen3:8b"
    assert client.select_model("not-installed") is False


def test_lists_models_loaded_in_memory(monkeypatch) -> None:
    def fake_urlopen(request, **_kwargs):
        url = request if isinstance(request, str) else request.full_url
        payload = {"models": [{"name": "qwen3:8b", "size_vram": 3_000_000_000, "context_length": 8192}]}
        assert url.endswith("/api/ps")
        return FakeResponse(json.dumps(payload).encode())

    monkeypatch.setattr("src.infrastructure.clients.ollama_client.urlopen", fake_urlopen)
    running = OllamaClient().list_running_models()
    assert running[0]["context_length"] == 8192
