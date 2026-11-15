"""Telegram Bot API — https://core.telegram.org/bots/api#sendmessage"""

from datetime import UTC, datetime

from app.platforms.base import Platform, PlatformError, PublishedPost

API_URL = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramPlatform(Platform):
    name = "Telegram"
    required_settings = ("telegram_bot_token", "telegram_chat_id")

    async def publish(self, message: str, link: str) -> PublishedPost:
        response = await self.client.post(
            API_URL.format(token=self.secret("telegram_bot_token")),
            json={"chat_id": self.settings.telegram_chat_id, "text": message},
        )
        try:
            data = response.json()
        except ValueError:
            data = {}
        if not data.get("ok"):
            # Telegram returns {"ok": false, "description": "..."} on errors.
            raise PlatformError(f"HTTP {response.status_code}: {data.get('description', 'request failed')}")

        result = data["result"]
        chat = result["chat"]
        message_id = result["message_id"]
        username = chat.get("username")

        if username:  # public channel or group: anyone can open t.me/<name>/<id>
            url, public = f"https://t.me/{username}/{message_id}", True
        elif str(chat["id"]).startswith("-100"):  # private channel: link works for members only
            url, public = f"https://t.me/c/{str(chat['id'])[4:]}/{message_id}", False
        else:
            url, public = None, False

        return PublishedPost(url=url, public_access=public, posted_at=datetime.fromtimestamp(result["date"], UTC))
