"""Create video tweet tool -- generates video via Replicate and posts via Blotato."""

import json
from typing import Annotated, Literal, Optional

import structlog
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from pydantic import Field

from content_automation.config import get_settings
from content_automation.server import mcp
from content_automation.services.blotato import BlotatoAPIError, get_blotato_service
from content_automation.services.replicate import ReplicateAPIError, get_replicate_service

logger = structlog.get_logger()


@mcp.tool
async def create_video_tweet(
    prompt: Annotated[str, Field(description="Text prompt for video generation via Replicate")],
    tweet_text: Annotated[str, Field(description="Tweet body text")],
    image_url: Annotated[str, Field(description="Input image URL for image-to-video generation")],
    aspect_ratio: Annotated[
        Literal["16:9", "9:16", "1:1"], Field(description="Video aspect ratio")
    ] = "16:9",
    num_frames: Annotated[
        Optional[int], Field(description="Number of frames (default from config)")
    ] = None,
    resolution: Annotated[
        Optional[str], Field(description="Video resolution, e.g. '720p' (default from config)")
    ] = None,
    frames_per_second: Annotated[
        Optional[int], Field(description="Frames per second (default from config)")
    ] = None,
    ctx: Context | None = None,
) -> str:
    """Generate a video from a prompt and post it as a tweet.

    Orchestrates the full pipeline: Replicate video generation -> Blotato tweet posting.
    Video generation typically takes 2-5 minutes. Progress updates are sent during generation.
    """
    # -- validate inputs --
    if not prompt or not prompt.strip():
        raise ToolError("Video prompt cannot be empty. Provide a descriptive prompt.")
    if not tweet_text or not tweet_text.strip():
        raise ToolError("Tweet text cannot be empty.")
    if not image_url or not image_url.strip():
        raise ToolError("Image URL is required for image-to-video generation.")

    # -- resolve defaults from config --
    settings = get_settings()
    num_frames = num_frames or settings.default_video_frames
    resolution = resolution or settings.default_video_resolution
    frames_per_second = frames_per_second or settings.default_video_fps

    # -- get services --
    replicate = get_replicate_service()
    blotato = get_blotato_service()

    # -- report initial progress --
    if ctx:
        await ctx.report_progress(progress=0, total=100)

    # -- create replicate prediction --
    try:
        prediction = await replicate.create_prediction(
            image=image_url,
            prompt=prompt,
            num_frames=num_frames,
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            frames_per_second=frames_per_second,
        )
    except ReplicateAPIError as e:
        raise ToolError(f"Failed to start video generation: {e}")

    prediction_id = prediction["id"]
    logger.info("video_tweet_prediction_created", prediction_id=prediction_id)

    if ctx:
        await ctx.report_progress(progress=10, total=100)

    # -- poll for completion --
    try:
        result = await replicate.poll_prediction(
            prediction_id, timeout=settings.video_generation_timeout
        )
    except TimeoutError as e:
        raise ToolError(str(e))
    except RuntimeError as e:
        raise ToolError(str(e))
    except ReplicateAPIError as e:
        raise ToolError(f"Video generation error: {e}")

    if ctx:
        await ctx.report_progress(progress=70, total=100)

    # -- extract video url (handle string or list output) --
    output = result.get("output")
    if isinstance(output, list):
        video_url = output[0]
    else:
        video_url = output

    logger.info("video_tweet_generation_complete", video_url=video_url)

    # -- post to blotato immediately (urls expire ~1hr) --
    if ctx:
        await ctx.report_progress(progress=80, total=100)

    try:
        post_result = await blotato.publish_post(
            text=tweet_text,
            media_urls=[video_url],
        )
    except BlotatoAPIError as e:
        raise ToolError(
            f"Video was generated but posting failed: {e}. "
            f"Video URL (expires soon): {video_url}"
        )

    submission_id = post_result.get("postSubmissionId")

    # -- try polling post status --
    try:
        status = await blotato.poll_post_status(submission_id, max_wait=30.0)
        public_url = status.get("publicUrl")
        post_status = status.get("status", "published")
    except BlotatoAPIError:
        public_url = None
        post_status = "pending"

    if ctx:
        await ctx.report_progress(progress=100, total=100)

    return json.dumps({
        "prediction_id": prediction_id,
        "video_url": video_url,
        "postSubmissionId": submission_id,
        "publicUrl": public_url,
        "status": post_status,
    })
