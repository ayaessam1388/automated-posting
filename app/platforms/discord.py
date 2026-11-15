"""Discord webhooks — https://discord.com/developers/docs/resources/webhook#execute-webhook"""

from app.platforms.base import Platform, PublishedPost, parse_json, parse_timestamp


class DiscordPlatform(Platform):
    name = "Discord"
    required_settings = ("discord_webhook_url",)

    async def publish(self, message: str, link: str) -> PublishedPost:
        webhook_url = self.secret("discord_webhook_url")
        response = await self.client.post(
            webhook_url,
            params={"wait": "true"},  # makes Discord return the created message
            json={"content": message, "allowed_mentions": {"parse": []}},
        )
        data = parse_json(response)

        guild_id = data.get("guild_id") or await self._guild_id(webhook_url)
        url = f"https://discord.com/channels/{guild_id}/{data['channel_id']}/{data['id']}" if guild_id else None

        # Discord messages are only visible to members of the server.
        return PublishedPost(url=url, public_access=False, posted_at=parse_timestamp(data.get("timestamp")))

    async def _guild_id(self, webhook_url: str) -> str | None:
        data = parse_json(await self.client.get(webhook_url))
        return data.get("guild_id")
