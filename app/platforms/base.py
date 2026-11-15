"""Common contract and helpers shared by every platform integration."""

import abc
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import Settings


class PlatformError(Exception):
    """A platform rejected the post; the message is safe to show to the API caller."""


class NotConfiguredError(PlatformError):
    """Required credentials for a platform are missing."""


@dataclass(slots=True)
class PublishedPost:
    url: str | None
    public_access: bool
    posted_at: datetime


class Platform(abc.ABC):
    """One third-party destination. Subclasses implement `publish`."""

    name: str
    # Settings attribute names that must be set before this platform can post.
    required_settings: tuple[str, ...] = ()

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.client = client

    def ensure_configured(self) -> None:
        missing = [
            attr.upper() for attr in self.required_settings if not _has_value(getattr(self.settings, attr))
        ]
        if missing:
            raise NotConfiguredError(f"Not configured: set {', '.join(missing)} in .env")

    def secret(self, attr: str) -> str:
        return getattr(self.settings, attr).get_secret_value()

    @abc.abstractmethod
    async def publish(self, message: str, link: str) -> PublishedPost:
        """Publish `message` (which contains `link`) and describe the created post."""


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return bool(str(value).strip())


def parse_json(response: httpx.Response) -> dict[str, Any]:
    """Return the JSON body, raising PlatformError with the platform's own message on failure."""
    try:
        data = response.json()
    except ValueError:
        data = {}

    if response.is_success:
        return data

    detail = None
    if isinstance(data, dict):
        parts = [str(data[key]) for key in ("error", "message", "description") if data.get(key)]
        detail = ": ".join(dict.fromkeys(parts)) or None
    raise PlatformError(f"HTTP {response.status_code}: {detail or response.reason_phrase or 'request failed'}")


def parse_timestamp(value: str | None) -> datetime:
    """Parse an ISO-8601 timestamp from an API, falling back to now (UTC)."""
    if value:
        try:
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime.now(UTC)
