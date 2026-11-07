from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = (
        "postgresql+psycopg://novelforge:novelforge-local-only@localhost:5432/novelforge"
    )
    app_env: str = "development"
    session_cookie_name: str = "novelforge_session"
    csrf_cookie_name: str = "novelforge_csrf"
    session_ttl_hours: int = 336
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "strict"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    ai_provider: str = "mock"
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_timeout_seconds: float = 30.0

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.app_env.lower() == "production":
            if "novelforge-local-only" in self.database_url:
                raise ValueError("DATABASE_URL must use a non-default production credential.")
            if not self.session_cookie_secure:
                raise ValueError("SESSION_COOKIE_SECURE must be enabled in production.")
            if not self.cors_origins.strip() or "localhost" in self.cors_origins:
                raise ValueError("CORS_ORIGINS must contain only deployed origins in production.")
        if self.session_cookie_samesite.lower() not in {"strict", "lax", "none"}:
            raise ValueError("SESSION_COOKIE_SAMESITE must be strict, lax or none.")
        if self.session_cookie_samesite.lower() == "none" and not self.session_cookie_secure:
            raise ValueError("SESSION_COOKIE_SECURE must be enabled when SameSite=None.")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
