"""Create video tweet tool stub for MCP server."""

from typing import Annotated, Literal

from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from pydantic import Field

from content_automation.server import mcp


@mcp.tool
async def create_video_tweet(
    prompt: Annotated[str, Field(description="Text prompt for video generation via Replicate")],
    tweet_text: Annotated[str, Field(description="Tweet body text")],
    image_url: Annotated[
        str | None, Field(description="Input image URL for image-to-video generation")
    ] = None,
    aspect_ratio: Annotated[
        Literal["16:9", "9:16", "1:1"], Field(description="Video aspect ratio")
    ] = "16:9",
    ctx: Context | None = None,
) -> str:
    """Generate a video from a prompt and post it as a tweet.

    Orchestrates the full pipeline: Replicate video generation -> Blotato tweet posting.
    Video generation typically takes 2-5 minutes. Progress updates are sent during generation.
    """
    if not prompt or not prompt.strip():
        raise ToolError("Video prompt cannot be empty. Provide a descriptive prompt.")
    if not tweet_text or not tweet_text.strip():
        raise ToolError("Tweet text cannot be empty.")

    # Phase 1: stub with progress demo
    if ctx:
        await ctx.report_progress(progress=0, total=100)
        await ctx.report_progress(progress=50, total=100)
        await ctx.report_progress(progress=100, total=100)

    prompt_preview = prompt[:50]
    tweet_preview = tweet_text[:50]
    return f"[STUB] Video tweet would be created. Prompt: '{prompt_preview}', Tweet: '{tweet_preview}'"
