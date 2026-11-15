"""Publishes one message to every platform concurrently, isolating failures."""

import asyncio
import logging
from datetime import UTC

import httpx

from app.platforms.base import Platform, PlatformError
from app.schemas import PlatformResult, PostingResponse, PostingSummary

logger = logging.getLogger("posting")


async def post_to_platform(platform: Platform, message: str, link: str) -> PlatformResult:
    """Post to a single platform. Never raises: every failure becomes a `failed` result."""
    try:
        platform.ensure_configured()
        post = await platform.publish(message, link)
    except PlatformError as exc:
        error = str(exc)
    except httpx.TimeoutException:
        error = "Request timed out"
    except httpx.RequestError as exc:
        # Do not echo the exception text: request URLs can embed secrets (e.g. Telegram bot tokens).
        error = f"Network error ({type(exc).__name__})"
    except Exception:
        logger.exception("Unexpected error while posting to %s", platform.name)
        error = "Unexpected error while posting"
    else:
        posted_at = post.posted_at.astimezone(UTC)
        logger.info("%s: success %s", platform.name, post.url)
        return PlatformResult(
            platform=platform.name,
            status="success",
            posted_url=post.url,
            public_access=post.public_access,
            date=posted_at.strftime("%Y-%m-%d"),
            time=posted_at.strftime("%H:%M:%S"),
        )

    logger.warning("%s: failed - %s", platform.name, error)
    return PlatformResult(platform=platform.name, status="failed", error=error)


async def post_everywhere(platforms: list[Platform], message: str, link: str) -> PostingResponse:
    results = await asyncio.gather(*(post_to_platform(p, message, link) for p in platforms))
    succeeded = sum(result.status == "success" for result in results)
    return PostingResponse(
        success=succeeded > 0,
        summary=PostingSummary(total=len(results), succeeded=succeeded, failed=len(results) - succeeded),
        results=list(results),
    )
