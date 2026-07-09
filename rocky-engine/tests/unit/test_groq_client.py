from src.infrastructure.clients.groq_client import GroqClient, _is_groq_auth_error


class AuthError(Exception):
    status_code = 401


class FakeCompletions:
    def __init__(self) -> None:
        self.calls = 0

    def create(self, **_kwargs: object) -> object:
        self.calls += 1
        raise AuthError("401 Unauthorized: Invalid API Key")


class FakeChat:
    def __init__(self, completions: FakeCompletions) -> None:
        self.completions = completions


class FakeGroqSdk:
    def __init__(self) -> None:
        self.completions = FakeCompletions()
        self.chat = FakeChat(self.completions)


def test_auth_error_is_detected() -> None:
    assert _is_groq_auth_error(AuthError("Invalid API Key"))


def test_auth_error_disables_client_without_retry(monkeypatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    client = GroqClient()
    fake = FakeGroqSdk()
    client._client = fake  # type: ignore[assignment]
    client._disabled_reason = None

    assert client.get_intent_json("hola", tools_prompt="") is None
    assert fake.completions.calls == 1
    assert client._client is None
    assert client._disabled_reason == "GROQ_API_KEY inválida o sin permisos"
