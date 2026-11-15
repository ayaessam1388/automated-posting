"""GitHub Gists — https://docs.github.com/en/rest/gists/gists#create-a-gist"""

from app.platforms.base import Platform, PublishedPost, parse_json, parse_timestamp


class GitHubGistPlatform(Platform):
    name = "GitHub Gist"
    required_settings = ("github_token",)

    async def publish(self, message: str, link: str) -> PublishedPost:
        response = await self.client.post(
            "https://api.github.com/gists",
            headers={
                "Authorization": f"Bearer {self.secret('github_token')}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={
                "description": message,
                "public": True,
                "files": {"post.md": {"content": message + "\n"}},
            },
        )
        data = parse_json(response)
        return PublishedPost(
            url=data.get("html_url"),
            public_access=bool(data.get("public")),
            posted_at=parse_timestamp(data.get("created_at")),
        )
