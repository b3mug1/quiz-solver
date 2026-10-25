import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    database_url: str = Field(default_factory=lambda: (
        "sqlite:////tmp/quiz_cache.db" if os.getenv("VERCEL") else "sqlite:///./quiz_cache.db"
    ))
    api_auth_secret: str = ""
    allowed_origins: str = ""
    log_level: str = "INFO"
    cache_ttl_seconds: int = 86400
    rate_limit_per_minute: int = 30
    max_batch_size: int = 20

    @property
    def origins(self) -> list[str]:
        return [part.strip() for part in self.allowed_origins.split(",") if part.strip()]
