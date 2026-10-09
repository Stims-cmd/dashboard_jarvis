"""Application settings, read from environment variables (see .env.example)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JARVIS_", env_file=".env", extra="ignore")

    secret_key: str = Field(min_length=32)
    admin_username: str = Field(min_length=1)
    password_hash: str = Field(pattern=r"^\$argon2")
    database_url: str = "sqlite:///data/jarvis.db"
    cookie_secure: bool = True
    session_hours: int = Field(default=8, ge=1, le=24 * 7)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
