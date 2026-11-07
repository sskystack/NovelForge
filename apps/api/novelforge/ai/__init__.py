"""Provider-neutral AI interfaces and adapters."""

from novelforge.ai.factory import create_chat_provider
from novelforge.ai.providers import (
    ChatMessage,
    ChatProvider,
    ChatResponse,
    EmbeddingProvider,
    MockProvider,
    ProviderError,
    ToolCall,
)

__all__ = [
    "ChatMessage",
    "ChatProvider",
    "ChatResponse",
    "EmbeddingProvider",
    "MockProvider",
    "ProviderError",
    "ToolCall",
    "create_chat_provider",
]
