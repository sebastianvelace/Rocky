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
