import json
from collections.abc import Iterator, Sequence
from urllib import error, request

from novelforge.ai.providers import (
    ChatMessage,
    ChatResponse,
    ChatStreamEvent,
    ProviderError,
    ToolCall,
)


class OpenAICompatibleProvider:
    """Small stdlib adapter for OpenAI-compatible chat endpoints."""

    def __init__(self, base_url: str, api_key: str, timeout_seconds: float = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def _request(self, endpoint: str, body: dict) -> request.Request:
        return request.Request(
            f"{self.base_url}/{endpoint}",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )

    @staticmethod
    def _body(messages: Sequence[ChatMessage], model: str, tools=()) -> dict:
        body = {"model": model, "messages": [message.__dict__ for message in messages]}
        if tools:
            body["tools"] = list(tools)
        return body

    def chat(
        self, messages: Sequence[ChatMessage], *, model: str, tools=(), response_schema=None
    ) -> ChatResponse:
        body = self._body(messages, model, tools)
        if response_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "novelforge_output", "schema": response_schema},
            }
        try:
            with request.urlopen(
                self._request("chat/completions", body), timeout=self.timeout_seconds
            ) as response:
                data = json.load(response)
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ProviderError("AI provider request failed") from exc
        try:
            choice = data["choices"][0]
            message = choice["message"]
            calls = tuple(
                ToolCall(
                    call["id"], call["function"]["name"], json.loads(call["function"]["arguments"])
                )
                for call in message.get("tool_calls", [])
            )
            content = message.get("content") or ""
            structured = json.loads(content) if response_schema is not None else None
            if structured is not None and not isinstance(structured, dict):
                raise TypeError("structured output must be an object")
            usage = data.get("usage", {})
            return ChatResponse(
                content=content,
                tool_calls=calls,
                model=data.get("model", model),
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                finish_reason=choice.get("finish_reason", "stop"),
                structured_output=structured,
                raw=data,
            )
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ProviderError("AI provider returned malformed response") from exc

    def stream(
        self, messages: Sequence[ChatMessage], *, model: str, tools=()
    ) -> Iterator[ChatStreamEvent]:
        body = self._body(messages, model, tools)
        body["stream"] = True
        tool_parts: dict[int, dict[str, str]] = {}
        usage: dict = {}
        finish_reason = "stop"
        try:
            with request.urlopen(
                self._request("chat/completions", body), timeout=self.timeout_seconds
            ) as response:
                for line in response:
                    if not line.startswith(b"data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == b"[DONE]":
                        break
                    chunk = json.loads(payload)
                    usage = chunk.get("usage") or usage
                    choices = chunk.get("choices", [])
                    if choices:
                        choice = choices[0]
                        finish_reason = choice.get("finish_reason") or finish_reason
                        delta = choice.get("delta", {})
                        for call in delta.get("tool_calls", []):
                            part = tool_parts.setdefault(
                                call["index"], {"id": "", "name": "", "arguments": ""}
                            )
                            part["id"] += call.get("id", "")
                            function = call.get("function", {})
                            part["name"] += function.get("name", "")
                            part["arguments"] += function.get("arguments", "")
                        if delta.get("content"):
                            yield ChatStreamEvent(content_delta=delta["content"])
            calls = tuple(
                ToolCall(value["id"], value["name"], json.loads(value["arguments"] or "{}"))
                for _, value in sorted(tool_parts.items())
            )
            yield ChatStreamEvent(
                tool_calls=calls,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                finish_reason=finish_reason,
            )
        except (error.URLError, TimeoutError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ProviderError("AI provider stream failed or returned malformed data") from exc

    def embed(self, texts: Sequence[str], *, model: str) -> list[list[float]]:
        try:
            with request.urlopen(
                self._request("embeddings", {"model": model, "input": list(texts)}),
                timeout=self.timeout_seconds,
            ) as response:
                data = json.load(response)
            vectors = [
                item["embedding"] for item in sorted(data["data"], key=lambda item: item["index"])
            ]
            if len(vectors) != len(texts) or any(
                not isinstance(vector, list) for vector in vectors
            ):
                raise TypeError("embedding count or shape is invalid")
            return vectors
        except (error.URLError, TimeoutError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ProviderError("AI provider returned malformed embeddings") from exc
