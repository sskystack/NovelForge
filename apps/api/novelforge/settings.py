from pathlib import Path

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
    session_cookie_name: str = "novelforge_session"
    csrf_cookie_name: str = "novelforge_csrf"
    session_ttl_hours: int = 336
    session_cookie_secure: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    ai_provider: str = "mock"
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_timeout_seconds: float = 30.0

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
