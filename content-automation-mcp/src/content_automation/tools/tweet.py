"""Create tweet tool -- posts to Twitter via Blotato API."""

import json
from typing import Annotated

import structlog
from fastmcp.exceptions import ToolError
from pydantic import Field

from content_automation.config import get_settings
from content_automation.resilience import ResilienceError
from content_automation.server import mcp
from content_automation.services.blotato import BlotatoAPIError, get_blotato_service

logger = structlog.get_logger()


@mcp.tool
async def create_tweet(
    text: Annotated[str, Field(description="Tweet body text (max 280 chars)")],
    media_urls: Annotated[
        list[str] | None, Field(description="Optional media URLs to attach")
    ] = None,
    thread_posts: Annotated[
        list[str] | None,
        Field(description="Additional posts for threading via Blotato additionalPosts"),
    ] = None,
) -> str:
    """Post a tweet via Blotato API.

    Creates a tweet with optional media attachments and thread support.
    Media URLs must be publicly accessible -- Blotato handles the transfer.
    """
    if not text or not text.strip():
        raise ToolError("Tweet text cannot be empty. Provide non-empty text.")
    if len(text) > 280:
        raise ToolError(
            f"Tweet text exceeds 280 characters (got {len(text)}). Shorten the text and retry."
        )

    # Validate media URLs
    if media_urls:
        for url in media_urls:
            if not url.startswith(("http://", "https://")):
                raise ToolError(
                    f"Invalid media URL: {url!r}. Media URLs must use http:// or https://."
                )

    # Dry-run guard -- return mock response without calling service
    settings = get_settings()
    if settings.dry_run:
        logger.info(
            "dry_run_skip",
            tool="create_tweet",
            text_preview=text[:50],
            media_count=len(media_urls) if media_urls else 0,
        )
        return json.dumps({
            "dry_run": True,
            "would_post": {
                "text": text,
                "media_urls": media_urls or [],
                "thread_posts": thread_posts or [],
            },
        })

    # Build additional posts for threading
    additional = None
    if thread_posts:
        additional = [{"text": t, "mediaUrls": []} for t in thread_posts]

    logger.info(
        "create_tweet",
        text_preview=text[:50],
        media_count=len(media_urls) if media_urls else 0,
        thread_count=len(thread_posts) if thread_posts else 0,
    )

    try:
        service = get_blotato_service()
        result = await service.publish_post(
            text=text,
            media_urls=media_urls,
            additional_posts=additional,
        )
        submission_id = result.get("postSubmissionId")

        # Try polling for the published URL
        try:
            status = await service.poll_post_status(submission_id, max_wait=30.0)
            return json.dumps(
                {
                    "postSubmissionId": submission_id,
                    "status": status.get("status", "published"),
                    "publicUrl": status.get("publicUrl"),
                }
            )
        except BlotatoAPIError:
            # Polling failed or timed out -- return submission confirmation
            return json.dumps(
                {
                    "postSubmissionId": submission_id,
                    "message": "Tweet submitted, status pending",
                }
            )

    except ResilienceError as e:
        raise ToolError(str(e))
    except BlotatoAPIError as e:
        raise ToolError(str(e))
