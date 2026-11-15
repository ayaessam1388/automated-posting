import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app, get_platforms
from app.platforms.base import Platform, PlatformError, PublishedPost
from app.platforms.bluesky import BlueskyPlatform, link_facet
from app.platforms.discord import DiscordPlatform
from app.platforms.github_gist import GitHubGistPlatform
from app.platforms.mastodon import MastodonPlatform
from app.platforms.telegram import TelegramPlatform
from app.services.posting_service import post_to_platform

VALID = "Check out our latest business platform and grow your online visibility. https://example.com"
LINK = "https://example.com"


# --------------------------------------------------------------------------- helpers


class FakePlatform(Platform):
    def __init__(self, name: str, error: Exception | None = None) -> None:
        self.name = name
        self.error = error

    def ensure_configured(self) -> None:
        pass

    async def publish(self, message: str, link: str) -> PublishedPost:
        if self.error:
            raise self.error
        return PublishedPost(
            url=f"https://{self.name.lower()}.test/post/1",
            public_access=True,
            posted_at=datetime(2026, 11, 15, 10, 30, 0, tzinfo=UTC),
        )


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def run_platform(platform_class, handler, **settings):
    """Run one real platform class against a mocked HTTP transport."""

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await post_to_platform(platform_class(Settings(_env_file=None, **settings), http), VALID, LINK)

    return asyncio.run(go())


# --------------------------------------------------------------------------- validation


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ({"message": "x" * 190 + " https://example.com"}, "must not exceed 200 characters"),
        ({"message": "No link in this message at all"}, "none found"),
        ({"message": "Two links https://a.com and https://b.com"}, "found 2"),
        ({"message": "Bare link www.example.com"}, "must start with http"),
        ({"message": "Bad domain https://example"}, "invalid domain"),
        ({"message": "IP link http://127.0.0.1/admin"}, "not an IP address"),
        ({"message": "Bad port https://example.com:99999"}, "invalid port"),
        ({"message": "   "}, "must not be empty"),
        ({}, "Field required"),
        ({"message": 123}, "valid string"),
    ],
)
def test_invalid_messages_are_rejected(client, body, expected):
    response = client.post("/posting", json=body)
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert expected in data["errors"][0]["message"]


def test_trailing_punctuation_is_not_part_of_the_link(client):
    app.dependency_overrides[get_platforms] = lambda: [FakePlatform("A")]
    response = client.post("/posting", json={"message": "Visit https://example.com/offer."})
    assert response.status_code == 200


# --------------------------------------------------------------------------- orchestration


def test_one_failure_does_not_stop_other_platforms(client):
    app.dependency_overrides[get_platforms] = lambda: [
        FakePlatform("Alpha"),
        FakePlatform("Beta", PlatformError("HTTP 401: Authentication failed")),
        FakePlatform("Gamma", httpx.ConnectError("boom")),
        FakePlatform("Delta"),
    ]
    response = client.post("/posting", json={"message": VALID})
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["summary"] == {"total": 4, "succeeded": 2, "failed": 2}
    by_name = {r["platform"]: r for r in data["results"]}
    assert by_name["Alpha"] == {
        "platform": "Alpha",
        "status": "success",
        "posted_url": "https://alpha.test/post/1",
        "public_access": True,
        "date": "2026-11-15",
        "time": "10:30:00",
        "error": None,
    }
    assert by_name["Beta"]["status"] == "failed"
    assert by_name["Beta"]["error"] == "HTTP 401: Authentication failed"
    assert by_name["Beta"]["date"] is None
    assert by_name["Gamma"]["error"] == "Network error (ConnectError)"


def test_all_failures_report_success_false(client):
    app.dependency_overrides[get_platforms] = lambda: [FakePlatform("A", PlatformError("nope"))]
    data = client.post("/posting", json={"message": VALID}).json()
    assert data["success"] is False


def test_unconfigured_platform_reports_missing_variables():
    result = run_platform(TelegramPlatform, lambda request: httpx.Response(500))
    assert result.status == "failed"
    assert result.error == "Not configured: set TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID in .env"


# --------------------------------------------------------------------------- platform integrations


def test_telegram_public_channel():
    def handler(request):
        assert request.url.path == "/botTOKEN/sendMessage"
        assert json.loads(request.content) == {"chat_id": "@mychannel", "text": VALID}
        return httpx.Response(
            200,
            json={"ok": True, "result": {"message_id": 42, "date": 1794738600, "chat": {"id": -1001, "username": "mychannel"}}},
        )

    result = run_platform(TelegramPlatform, handler, telegram_bot_token="TOKEN", telegram_chat_id="@mychannel")
    assert result.status == "success"
    assert result.posted_url == "https://t.me/mychannel/42"
    assert result.public_access is True


def test_telegram_error_does_not_leak_token():
    def handler(request):
        return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})

    result = run_platform(TelegramPlatform, handler, telegram_bot_token="SECRET", telegram_chat_id="@c")
    assert result.error == "HTTP 401: Unauthorized"
    assert "SECRET" not in result.error


def test_discord_webhook():
    def handler(request):
        assert request.url.params["wait"] == "true"
        return httpx.Response(
            200, json={"id": "3", "channel_id": "2", "guild_id": "1", "timestamp": "2026-11-15T10:30:00+00:00"}
        )

    result = run_platform(DiscordPlatform, handler, discord_webhook_url="https://discord.com/api/webhooks/1/abc")
    assert result.posted_url == "https://discord.com/channels/1/2/3"
    assert result.public_access is False
    assert (result.date, result.time) == ("2026-11-15", "10:30:00")


def test_mastodon_status_and_error():
    def ok(request):
        assert request.headers["Authorization"] == "Bearer TOKEN"
        return httpx.Response(
            200,
            json={"url": "https://mastodon.social/@me/1", "visibility": "public", "created_at": "2026-11-15T10:30:00.000Z"},
        )

    result = run_platform(MastodonPlatform, ok, mastodon_access_token="TOKEN")
    assert result.posted_url == "https://mastodon.social/@me/1"
    assert result.public_access is True

    result = run_platform(
        MastodonPlatform, lambda r: httpx.Response(401, json={"error": "The access token is invalid"}), mastodon_access_token="T"
    )
    assert result.error == "HTTP 401: The access token is invalid"


def test_bluesky_session_then_post():
    def handler(request):
        if request.url.path.endswith("createSession"):
            return httpx.Response(200, json={"accessJwt": "JWT", "did": "did:plc:abc", "handle": "me.bsky.social"})
        body = json.loads(request.content)
        assert request.headers["Authorization"] == "Bearer JWT"
        assert body["record"]["facets"][0]["features"][0]["uri"] == LINK
        return httpx.Response(200, json={"uri": "at://did:plc:abc/app.bsky.feed.post/3kxyz", "cid": "c"})

    result = run_platform(BlueskyPlatform, handler, bluesky_handle="me.bsky.social", bluesky_app_password="pw")
    assert result.posted_url == "https://bsky.app/profile/me.bsky.social/post/3kxyz"


def test_bluesky_facet_uses_utf8_byte_offsets():
    message = "زوروا موقعنا https://example.com"
    facet = link_facet(message, LINK)
    raw = message.encode("utf-8")
    assert raw[facet["index"]["byteStart"] : facet["index"]["byteEnd"]].decode() == LINK


def test_github_gist():
    def handler(request):
        body = json.loads(request.content)
        assert body["public"] is True
        return httpx.Response(
            201, json={"html_url": "https://gist.github.com/me/abc", "public": True, "created_at": "2026-11-15T10:30:00Z"}
        )

    result = run_platform(GitHubGistPlatform, handler, github_token="TOKEN")
    assert result.posted_url == "https://gist.github.com/me/abc"
    assert result.public_access is True


def test_timeout_is_reported():
    def handler(request):
        raise httpx.ReadTimeout("slow")

    result = run_platform(GitHubGistPlatform, handler, github_token="TOKEN")
    assert result.error == "Request timed out"
