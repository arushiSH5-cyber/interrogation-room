"""ClaudeLLM tests with a stand-in for the Anthropic client (no network)."""
from types import SimpleNamespace

import pytest

from src.llm import ClaudeLLM, LLMError


class StubMessages:
    def __init__(self, text, stop_reason="end_turn"):
        self.text, self.stop_reason, self.kwargs = text, stop_reason, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.text)],
            stop_reason=self.stop_reason,
            usage=SimpleNamespace(input_tokens=10, output_tokens=5))


def make(text, stop_reason="end_turn", model="claude-haiku-5-5"):
    messages = StubMessages(text, stop_reason)
    llm = ClaudeLLM(model=model, client=SimpleNamespace(messages=messages))
    return llm, messages


def test_json_sends_schema_and_parses_reply():
    llm, stub = make('{"facts": []}')
    assert llm.json("sys", [{"role": "user", "content": "hi"}], {"type": "object"}) == {"facts": []}
    assert stub.kwargs["output_config"]["format"]["type"] == "json_schema"
    assert llm.calls == 1 and llm.input_tokens == 10


def test_fallback_only_for_supported_models():
    _, stub = make("ok")
    ClaudeLLM(model="claude-haiku-5-5", client=SimpleNamespace(messages=stub)).chat("s", [])
    assert "extra_body" not in stub.kwargs
    ClaudeLLM(model="claude-opus-5-5", client=SimpleNamespace(messages=stub)).chat("s", [])
    assert stub.kwargs["extra_body"] == {"fallbacks": "default"}


@pytest.mark.parametrize("reason", ["refusal", "max_tokens"])
def test_unusable_replies_raise(reason):
    llm, _ = make("", stop_reason=reason)
    with pytest.raises(LLMError):
        llm.chat("s", [])


def test_missing_key_gives_helpful_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)  # ignore a real .env
    with pytest.raises(LLMError, match=".env"):
        ClaudeLLM()


class FailingMessages:
    def __init__(self, error):
        self.error = error

    def create(self, **kwargs):
        raise self.error


@pytest.mark.parametrize("error_class, message", [
    ("APIConnectionError", "internet"),
    ("AuthenticationError", "API key"),
    ("RateLimitError", "Rate limited"),
])
def test_api_errors_become_friendly_llm_errors(error_class, message):
    import anthropic
    cls = getattr(anthropic, error_class)
    error = cls.__new__(cls)          # skip the SDK constructor (needs a real HTTP request)
    llm = ClaudeLLM(model="claude-haiku-5-5", client=SimpleNamespace(messages=FailingMessages(error)))
    with pytest.raises(LLMError, match=message):
        llm.chat("s", [])


def test_model_can_be_set_in_env(monkeypatch):
    monkeypatch.setenv("IR_MODEL", "claude-sonnet-5-5")
    llm = ClaudeLLM(client=SimpleNamespace(messages=StubMessages("ok")))
    assert llm.model == "claude-sonnet-5-5"


def test_default_model_is_haiku(monkeypatch):
    monkeypatch.delenv("IR_MODEL", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    assert ClaudeLLM(client=SimpleNamespace(messages=StubMessages("ok"))).model == "claude-haiku-5-5"
