from novelforge.ai.openai_compatible import OpenAICompatibleProvider
from novelforge.ai.providers import ChatProvider, MockProvider, ProviderError
from novelforge.settings import Settings


def create_chat_provider(settings: Settings) -> ChatProvider:
    if settings.ai_provider == "mock":
        return MockProvider()
    if settings.ai_provider == "openai-compatible":
        if not settings.ai_base_url or not settings.ai_api_key:
            raise ProviderError("AI provider configuration is incomplete")
        return OpenAICompatibleProvider(
            settings.ai_base_url, settings.ai_api_key, settings.ai_timeout_seconds
        )
    raise ProviderError(f"Unsupported AI provider: {settings.ai_provider}")
