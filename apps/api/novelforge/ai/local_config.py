"""Author-scoped local configuration. Secrets never appear in response schemas."""

from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from novelforge.ai.agent_models import LocalAIConfig
from novelforge.ai.factory import create_chat_provider
from novelforge.ai.providers import ChatMessage
from novelforge.database import get_db
from novelforge.errors import Problem
from novelforge.identity.dependencies import get_current_user, require_csrf
from novelforge.identity.models import User
from novelforge.settings import Settings

router = APIRouter(prefix="/settings/ai", tags=["local-ai-settings"])


def validate_endpoint(value: str) -> str:
    if not value:
        return value
    parsed = urlparse(value)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Use a base URL without credentials, query or fragment.")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Use an HTTP(S) endpoint.")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Unencrypted HTTP is permitted only for loopback model servers.")
    return value.rstrip("/")


class AIConfigPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["mock", "openai-compatible"] | None = None
    base_url: str | None = Field(default=None, max_length=2000)
    chat_model: str | None = Field(default=None, min_length=1, max_length=200)
    embedding_model: str | None = Field(default=None, min_length=1, max_length=200)
    timeout_seconds: float | None = Field(default=None, ge=1, le=120)
    api_key: str | None = Field(default=None, max_length=4000, repr=False)

    @field_validator("base_url")
    @classmethod
    def endpoint(cls, value):
        return validate_endpoint(value) if value is not None else value


def effective_settings(db: Session, owner_id: UUID, defaults: Settings) -> Settings:
    row = db.get(LocalAIConfig, owner_id)
    if row is None:
        return defaults
    return defaults.model_copy(
        update={f"ai_{key}": value for key, value in row.configuration.items()}
    )


def masked(settings: Settings) -> dict:
    return {
        "provider": settings.ai_provider,
        "base_url": settings.ai_base_url,
        "chat_model": settings.ai_chat_model,
        "embedding_model": settings.ai_embedding_model,
        "timeout_seconds": settings.ai_timeout_seconds,
        "api_key_configured": bool(settings.ai_api_key),
    }


@router.get("")
def get_settings(
    request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return masked(effective_settings(db, user.id, request.app.state.settings))


@router.patch("")
def patch_settings(
    payload: AIConfigPatch,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    row = db.get(LocalAIConfig, user.id)
    if row is None:
        row = LocalAIConfig(owner_id=user.id, configuration={})
        db.add(row)
    row.configuration = {**row.configuration, **payload.model_dump(exclude_none=True)}
    db.commit()
    return masked(effective_settings(db, user.id, request.app.state.settings))


@router.post("/test")
async def test_settings(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    import asyncio

    from novelforge.ai.agent_service import blocking_call

    settings = effective_settings(db, user.id, request.app.state.settings)
    try:
        provider = create_chat_provider(settings)
        result = await asyncio.wait_for(
            blocking_call(
                provider.chat,
                [ChatMessage("user", "Reply briefly with OK. No user data is included.")],
                model=settings.ai_chat_model,
            ),
            timeout=settings.ai_timeout_seconds,
        )
        if not result.content.strip():
            raise ValueError("empty response")
    except Exception as exc:
        raise Problem(
            502,
            "MODEL_CONNECTION_FAILED",
            "Model connection failed",
            "The model could not complete the connection test. Check its URL and settings.",
        ) from exc
    return {
        "ok": True,
        "provider": settings.ai_provider,
        "model": settings.ai_chat_model,
        "message": "Mock profile is available offline."
        if settings.ai_provider == "mock"
        else "The configured model completed the connection test.",
    }
