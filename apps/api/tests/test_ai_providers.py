import json
from urllib import request

import pytest

from novelforge.ai.openai_compatible import OpenAICompatibleProvider
from novelforge.ai.providers import ChatMessage, MockProvider, ProviderError


def test_mock_provider_is_deterministic_and_normalizes_tools() -> None:
    provider = MockProvider()
    messages = [ChatMessage("user", "写一个开场")]
    first = provider.chat(messages, model="mock", tools=[{"name": "save_draft"}])
    second = provider.chat(messages, model="mock", tools=[{"name": "save_draft"}])
    assert first == second
    assert first.tool_calls[0].name == "save_draft"
    assert provider.embed(["a", "b"]) == provider.embed(["a", "b"])


def test_openai_compatible_provider_normalizes_response(monkeypatch) -> None:
    response = {
        "model": "test-model",
        "choices": [
            {
                "message": {
                    "content": "ok",
                    "tool_calls": [{"id": "1", "function": {"name": "x", "arguments": "{}"}}],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 2, "completion_tokens": 1},
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def __iter__(self):
            return iter(())

    monkeypatch.setattr(request, "urlopen", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(json, "load", lambda _: response)
    result = OpenAICompatibleProvider("https://example.test", "secret").chat(
        [ChatMessage("user", "hello")], model="test-model"
    )
    assert result.content == "ok"
    assert result.tool_calls[0].name == "x"
    assert result.prompt_tokens == 2


def test_openai_compatible_provider_rejects_malformed_response(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(request, "urlopen", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(json, "load", lambda _: {"choices": []})
    with pytest.raises(ProviderError):
        OpenAICompatibleProvider("https://example.test", "secret").chat(
            [ChatMessage("user", "hello")], model="test-model"
        )


def test_openai_compatible_provider_maps_timeout_without_exposing_secret(monkeypatch) -> None:
    def timeout(*args, **kwargs):
        raise TimeoutError("secret timed out")

    monkeypatch.setattr(request, "urlopen", timeout)
    with pytest.raises(ProviderError, match="AI provider request failed") as error:
        OpenAICompatibleProvider("https://example.test", "secret").chat(
            [ChatMessage("user", "hello")], model="test-model"
        )
    assert "secret" not in str(error.value)


def test_openai_compatible_provider_parses_structured_output(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(request, "urlopen", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(
        json,
        "load",
        lambda _: {"choices": [{"message": {"content": '{"title":"Draft"}'}}]},
    )
    result = OpenAICompatibleProvider("https://example.test", "secret").chat(
        [ChatMessage("user", "hello")],
        model="test-model",
        response_schema={"type": "object"},
    )
    assert result.structured_output == {"title": "Draft"}
