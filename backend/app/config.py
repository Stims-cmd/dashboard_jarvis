"""Application settings, read from environment variables (see .env.example)."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.auth.totp import is_valid_secret


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JARVIS_", env_file=".env", extra="ignore")

    secret_key: str = Field(min_length=32)
    admin_username: str = Field(min_length=1)
    password_hash: str = Field(pattern=r"^\$argon2")
    database_url: str = "sqlite:///data/jarvis.db"
    cookie_secure: bool = True
    session_hours: int = Field(default=8, ge=1, le=24 * 7)
    # Base32 TOTP secret (python -m app.totp_setup). Empty: no second factor.
    totp_secret: SecretStr | None = None

    # Claude API (optional): summaries are skipped when the key is missing.
    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    llm_model: str = "claude-haiku-5-5"
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
        "totp_secret",
        "anthropic_api_key",
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

    @field_validator("totp_secret")
    @classmethod
    def totp_secret_is_base32(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not is_valid_secret(value.get_secret_value()):
            raise ValueError("must be a base32 secret of at least 128 bits (app.totp_setup)")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
