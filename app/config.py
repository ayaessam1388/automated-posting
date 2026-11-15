"""Application settings, loaded from environment variables or a local `.env` file."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    request_timeout: float = 15.0

    # Telegram
    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None

    # Discord
    discord_webhook_url: SecretStr | None = None

    # Mastodon
    mastodon_instance_url: str = "https://mastodon.social"
    mastodon_access_token: SecretStr | None = None

    # Bluesky
    bluesky_service_url: str = "https://bsky.social"
    bluesky_handle: str | None = None
    bluesky_app_password: SecretStr | None = None

    # GitHub Gist
    github_token: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
