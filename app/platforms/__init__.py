"""Registry of every platform the application posts to."""

import httpx

from app.config import Settings
from app.platforms.base import Platform
from app.platforms.bluesky import BlueskyPlatform
from app.platforms.discord import DiscordPlatform
from app.platforms.github_gist import GitHubGistPlatform
from app.platforms.mastodon import MastodonPlatform
from app.platforms.telegram import TelegramPlatform

PLATFORM_CLASSES: tuple[type[Platform], ...] = (
    TelegramPlatform,
    DiscordPlatform,
    MastodonPlatform,
    BlueskyPlatform,
    GitHubGistPlatform,
)


def build_platforms(settings: Settings, client: httpx.AsyncClient) -> list[Platform]:
    return [platform_class(settings, client) for platform_class in PLATFORM_CLASSES]
