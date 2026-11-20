from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Protocol


class ProviderError(RuntimeError):
    """A provider failed or returned a response that cannot be normalized."""


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str
    tool_calls: tuple["ToolCall", ...] = ()
    tool_call_id: str | None = None


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ChatResponse:
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str = "stop"
    structured_output: dict[str, Any] | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class ChatStreamEvent:
    content_delta: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str | None = None


class ChatProvider(Protocol):
    def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str,
        tools: Sequence[dict[str, Any]] = (),
        response_schema: dict[str, Any] | None = None,
        max_output_tokens: int | None = None,
    ) -> ChatResponse: ...

    def stream(
        self, messages: Sequence[ChatMessage], *, model: str, tools: Sequence[dict[str, Any]] = ()
    ) -> Iterator[ChatStreamEvent]: ...


class EmbeddingProvider(Protocol):
    def embed(self, texts: Sequence[str], *, model: str) -> list[list[float]]: ...


class MockProvider:
    """Deterministic provider used by tests and local development."""

    def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str = "mock-chat",
        tools=(),
        response_schema=None,
        max_output_tokens=None,
    ) -> ChatResponse:
        prompt = "\n".join(message.content for message in messages)
        digest = sha256(prompt.encode("utf-8")).hexdigest()[:12]
        calls = ()
        if tools and not any(message.role == "tool" for message in messages):
            # Exercise one useful read, then finish after its observation. The mock
            # never fabricates a write request and does not loop indefinitely.
            tool = next(
                (
                    item
                    for item in tools
                    if item.get("function", item).get("name") == "read_outline"
                ),
                tools[0],
            )
            name = str(tool.get("function", tool)["name"])
            calls = (ToolCall(f"mock-{digest}", name, {}),)
        return ChatResponse(
            content=f"Mock response [{digest}]: {prompt[-200:]}",
            tool_calls=calls,
            model=model,
            prompt_tokens=len(prompt.split()),
            completion_tokens=4,
            structured_output={} if response_schema else None,
            raw={"provider": "mock"},
        )

    def stream(self, messages: Sequence[ChatMessage], *, model: str = "mock-chat", tools=()):
        response = self.chat(messages, model=model, tools=tools)
        yield ChatStreamEvent(content_delta=response.content, finish_reason="stop")

    def embed(self, texts: Sequence[str], *, model: str = "mock-embedding") -> list[list[float]]:
        return [[(byte / 255.0) for byte in sha256(text.encode()).digest()[:8]] for text in texts]
