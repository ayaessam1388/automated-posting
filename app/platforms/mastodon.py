"""Mastodon — https://docs.joinmastodon.org/methods/statuses/#create"""

import uuid

from app.platforms.base import Platform, PublishedPost, parse_json, parse_timestamp


class MastodonPlatform(Platform):
    name = "Mastodon"
    required_settings = ("mastodon_instance_url", "mastodon_access_token")

    async def publish(self, message: str, link: str) -> PublishedPost:
        instance = self.settings.mastodon_instance_url.rstrip("/")
        response = await self.client.post(
            f"{instance}/api/v1/statuses",
            headers={
                "Authorization": f"Bearer {self.secret('mastodon_access_token')}",
                "Idempotency-Key": str(uuid.uuid4()),
            },
            json={"status": message, "visibility": "public"},
        )
        data = parse_json(response)
        return PublishedPost(
            url=data.get("url"),
            public_access=data.get("visibility") == "public",
            posted_at=parse_timestamp(data.get("created_at")),
        )
