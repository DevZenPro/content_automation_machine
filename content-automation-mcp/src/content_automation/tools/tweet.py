"""Create tweet tool stub for MCP server."""

from typing import Annotated

from fastmcp.exceptions import ToolError
from pydantic import Field

from content_automation.server import mcp


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

    preview = f"'{text[:50]}...'" if len(text) > 50 else f"'{text}'"
    return f"[STUB] Tweet would be posted: {preview}"
