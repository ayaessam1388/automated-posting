"""Bluesky (AT Protocol) — https://docs.bsky.app/docs/advanced-guides/posts"""

from datetime import UTC, datetime

from app.platforms.base import Platform, PublishedPost, parse_json


def link_facet(message: str, link: str) -> dict:
    """Build the rich-text facet that makes `link` clickable. Offsets are UTF-8 byte indexes."""
    start = len(message[: message.index(link)].encode("utf-8"))
    return {
        "index": {"byteStart": start, "byteEnd": start + len(link.encode("utf-8"))},
        "features": [{"$type": "app.bsky.richtext.facet#link", "uri": link}],
    }


class BlueskyPlatform(Platform):
    name = "Bluesky"
    required_settings = ("bluesky_service_url", "bluesky_handle", "bluesky_app_password")

    async def publish(self, message: str, link: str) -> PublishedPost:
        service = self.settings.bluesky_service_url.rstrip("/")

        session = parse_json(
            await self.client.post(
                f"{service}/xrpc/com.atproto.server.createSession",
                json={
                    "identifier": self.settings.bluesky_handle,
                    "password": self.secret("bluesky_app_password"),
                },
            )
        )

        posted_at = datetime.now(UTC)
        record = {
            "$type": "app.bsky.feed.post",
            "text": message,
            "createdAt": posted_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "facets": [link_facet(message, link)],
        }
        data = parse_json(
            await self.client.post(
                f"{service}/xrpc/com.atproto.repo.createRecord",
                headers={"Authorization": f"Bearer {session['accessJwt']}"},
                json={"repo": session["did"], "collection": "app.bsky.feed.post", "record": record},
            )
        )

        # uri looks like at://did:plc:xxx/app.bsky.feed.post/<rkey>
        rkey = data["uri"].rsplit("/", 1)[-1]
        url = f"https://bsky.app/profile/{session['handle']}/post/{rkey}"
        return PublishedPost(url=url, public_access=True, posted_at=posted_at)
