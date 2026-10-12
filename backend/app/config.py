"""Application settings, read from environment variables (see .env.example)."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JARVIS_", env_file=".env", extra="ignore")

    secret_key: str = Field(min_length=32)
    admin_username: str = Field(min_length=1)
    password_hash: str = Field(pattern=r"^\$argon2")
    database_url: str = "sqlite:///data/jarvis.db"
    cookie_secure: bool = True
    session_hours: int = Field(default=8, ge=1, le=24 * 7)

    # Claude API (optional): summaries are skipped when the key is missing.
    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    llm_model: str = "claude-haiku-5-5"
    # NVD API key (optional): raises the NVD rate limit from 5 to 50 requests / 30 s.
    nvd_api_key: SecretStr | None = None
    # List of software the owner already knows (one "- name" per line).
    skills_file: Path = Path("/config/skills.md")
    # OSINT: identifiers to watch (never committed) and Brave Search key (optional).
    osint_file: Path = Path("/config/osint.toml")
    brave_api_key: SecretStr | None = None
    # Leboncoin: dedicated mailbox receiving the saved-search alerts, read over IMAP.
    lbc_imap_host: str | None = None
    lbc_imap_port: int = Field(default=993, ge=1, le=65535)
    lbc_imap_username: str | None = None
    lbc_imap_password: SecretStr | None = None
    lbc_imap_folder: str = "INBOX"

    @field_validator(
        "anthropic_api_key",
        "nvd_api_key",
        "brave_api_key",
        "lbc_imap_host",
        "lbc_imap_username",
        "lbc_imap_password",
        mode="before",
    )
    @classmethod
    def empty_means_missing(cls, value: object) -> object:
        # "ANTHROPIC_API_KEY=" left empty in .env must not count as a key.
        return None if isinstance(value, str) and not value.strip() else value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
