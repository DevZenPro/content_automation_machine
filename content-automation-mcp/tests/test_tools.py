"""Tool-specific tests: service integration, validation errors, media and threading."""

import json
from unittest.mock import AsyncMock, patch

from content_automation.services.blotato import BlotatoAPIError
from content_automation.services.replicate import ReplicateAPIError

# -- create_tweet tests -------------------------------------------------------


def _mock_blotato_service(publish_return=None, poll_return=None, poll_error=None):
    """Build a mock BlotatoService with configurable responses."""
    service = AsyncMock()
    service.publish_post.return_value = publish_return or {
        "postSubmissionId": "test-uuid-123"
    }
    if poll_error:
        service.poll_post_status.side_effect = poll_error
    else:
        service.poll_post_status.return_value = poll_return or {
            "status": "published",
            "publicUrl": "https://twitter.com/user/status/123",
        }
    return service


@patch("content_automation.tools.tweet.get_blotato_service")
async def test_create_tweet_posts_via_blotato(mock_get_service, mcp_client):
    """Calling create_tweet posts via BlotatoService and returns publicUrl."""
    mock_service = _mock_blotato_service()
    mock_get_service.return_value = mock_service

    result = await mcp_client.call_tool("create_tweet", {"text": "Hello world"})
    data = json.loads(result.content[0].text)

    assert data["postSubmissionId"] == "test-uuid-123"
    assert data["publicUrl"] == "https://twitter.com/user/status/123"
    assert data["status"] == "published"
    mock_service.publish_post.assert_called_once_with(
        text="Hello world", media_urls=None, additional_posts=None
    )


async def test_create_tweet_empty_text_error(mcp_client):
    """Empty tweet text produces an error result mentioning 'cannot be empty'."""
    result = await mcp_client.call_tool(
        "create_tweet", {"text": ""}, raise_on_error=False
    )
    assert result.is_error is True
    assert "cannot be empty" in result.content[0].text.lower()


async def test_create_tweet_too_long_error(mcp_client):
    """Tweet text over 280 chars produces an error mentioning '280'."""
    long_text = "x" * 281
    result = await mcp_client.call_tool(
        "create_tweet", {"text": long_text}, raise_on_error=False
    )
    assert result.is_error is True
    assert "280" in result.content[0].text


@patch("content_automation.tools.tweet.get_blotato_service")
async def test_create_tweet_with_media_urls(mock_get_service, mcp_client):
    """create_tweet with media_urls passes them to publish_post."""
    mock_service = _mock_blotato_service()
    mock_get_service.return_value = mock_service

    result = await mcp_client.call_tool(
        "create_tweet",
        {"text": "Check this out", "media_urls": ["https://example.com/img.jpg"]},
    )
    data = json.loads(result.content[0].text)
    assert data["postSubmissionId"] == "test-uuid-123"

    mock_service.publish_post.assert_called_once_with(
        text="Check this out",
        media_urls=["https://example.com/img.jpg"],
        additional_posts=None,
    )


@patch("content_automation.tools.tweet.get_blotato_service")
async def test_create_tweet_with_thread_posts(mock_get_service, mcp_client):
    """create_tweet with thread_posts converts to additionalPosts format."""
    mock_service = _mock_blotato_service()
    mock_get_service.return_value = mock_service

    result = await mcp_client.call_tool(
        "create_tweet",
        {"text": "Thread start", "thread_posts": ["Reply 1", "Reply 2"]},
    )
    data = json.loads(result.content[0].text)
    assert data["postSubmissionId"] == "test-uuid-123"

    mock_service.publish_post.assert_called_once_with(
        text="Thread start",
        media_urls=None,
        additional_posts=[
            {"text": "Reply 1", "mediaUrls": []},
            {"text": "Reply 2", "mediaUrls": []},
        ],
    )


@patch("content_automation.tools.tweet.get_blotato_service")
async def test_create_tweet_api_error_surfaces_as_tool_error(
    mock_get_service, mcp_client
):
    """BlotatoAPIError from service is surfaced as ToolError (is_error=True)."""
    mock_service = AsyncMock()
    mock_service.publish_post.side_effect = BlotatoAPIError(
        "Client error 401: Unauthorized", status_code=401
    )
    mock_get_service.return_value = mock_service

    result = await mcp_client.call_tool(
        "create_tweet", {"text": "Should fail"}, raise_on_error=False
    )
    assert result.is_error is True
    assert "401" in result.content[0].text


@patch("content_automation.tools.tweet.get_blotato_service")
async def test_create_tweet_polling_timeout_returns_pending(
    mock_get_service, mcp_client
):
    """When polling times out, returns submission confirmation with pending status."""
    mock_service = _mock_blotato_service(
        poll_error=BlotatoAPIError("Post test-uuid-123 did not complete within 30.0s")
    )
    mock_get_service.return_value = mock_service

    result = await mcp_client.call_tool("create_tweet", {"text": "Slow post"})
    data = json.loads(result.content[0].text)

    assert data["postSubmissionId"] == "test-uuid-123"
    assert data["message"] == "Tweet submitted, status pending"


# -- create_video_tweet tests -------------------------------------------------


def _mock_replicate_service(
    create_return=None, poll_return=None, poll_error=None,
):
    """Build a mock ReplicateService with configurable responses."""
    service = AsyncMock()
    service.create_prediction.return_value = create_return or {
        "id": "pred-123",
        "status": "starting",
    }
    if poll_error:
        service.poll_prediction.side_effect = poll_error
    else:
        service.poll_prediction.return_value = poll_return or {
            "status": "succeeded",
            "output": "https://replicate.delivery/video.mp4",
        }
    return service


async def test_create_video_tweet_empty_prompt_error(mcp_client):
    """Empty video prompt produces an isError=True result."""
    result = await mcp_client.call_tool(
        "create_video_tweet",
        {"prompt": "", "tweet_text": "Some text", "image_url": "https://img.jpg"},
        raise_on_error=False,
    )
    assert result.is_error is True


async def test_create_video_tweet_empty_tweet_text_error(mcp_client):
    """Empty tweet_text in create_video_tweet produces an isError=True result."""
    result = await mcp_client.call_tool(
        "create_video_tweet",
        {"prompt": "A valid prompt", "tweet_text": "", "image_url": "https://img.jpg"},
        raise_on_error=False,
    )
    assert result.is_error is True


@patch("content_automation.tools.video_tweet.get_blotato_service")
@patch("content_automation.tools.video_tweet.get_replicate_service")
async def test_create_video_tweet_full_pipeline(
    mock_get_replicate, mock_get_blotato, mcp_client
):
    """Full pipeline: create prediction -> poll -> post tweet."""
    mock_replicate = _mock_replicate_service()
    mock_get_replicate.return_value = mock_replicate

    mock_blotato = _mock_blotato_service(
        publish_return={"postSubmissionId": "sub-456"},
        poll_return={
            "status": "published",
            "publicUrl": "https://twitter.com/status/789",
        },
    )
    mock_get_blotato.return_value = mock_blotato

    result = await mcp_client.call_tool(
        "create_video_tweet",
        {
            "prompt": "A sunset over the ocean",
            "tweet_text": "Beautiful sunset",
            "image_url": "https://example.com/photo.jpg",
        },
    )
    data = json.loads(result.content[0].text)

    assert data["prediction_id"] == "pred-123"
    assert data["video_url"] == "https://replicate.delivery/video.mp4"
    assert data["postSubmissionId"] == "sub-456"
    assert data["publicUrl"] == "https://twitter.com/status/789"

    mock_blotato.publish_post.assert_called_once_with(
        text="Beautiful sunset",
        media_urls=["https://replicate.delivery/video.mp4"],
    )


@patch("content_automation.tools.video_tweet.get_blotato_service")
@patch("content_automation.tools.video_tweet.get_replicate_service")
async def test_create_video_tweet_timeout_error(
    mock_get_replicate, mock_get_blotato, mcp_client
):
    """Replicate timeout surfaces as ToolError with 'timed out' message."""
    mock_replicate = _mock_replicate_service(
        poll_error=TimeoutError("Video generation timed out after 300s")
    )
    mock_get_replicate.return_value = mock_replicate
    mock_get_blotato.return_value = _mock_blotato_service()

    result = await mcp_client.call_tool(
        "create_video_tweet",
        {
            "prompt": "A sunset",
            "tweet_text": "Beautiful",
            "image_url": "https://example.com/photo.jpg",
        },
        raise_on_error=False,
    )
    assert result.is_error is True
    assert "timed out" in result.content[0].text.lower()


@patch("content_automation.tools.video_tweet.get_blotato_service")
@patch("content_automation.tools.video_tweet.get_replicate_service")
async def test_create_video_tweet_generation_failure(
    mock_get_replicate, mock_get_blotato, mcp_client
):
    """Replicate generation failure surfaces as ToolError."""
    mock_replicate = _mock_replicate_service(
        poll_error=RuntimeError("Video generation failed: OOM. Prediction ID: pred-123")
    )
    mock_get_replicate.return_value = mock_replicate
    mock_get_blotato.return_value = _mock_blotato_service()

    result = await mcp_client.call_tool(
        "create_video_tweet",
        {
            "prompt": "A sunset",
            "tweet_text": "Beautiful",
            "image_url": "https://example.com/photo.jpg",
        },
        raise_on_error=False,
    )
    assert result.is_error is True
    assert "oom" in result.content[0].text.lower()


@patch("content_automation.tools.video_tweet.get_blotato_service")
@patch("content_automation.tools.video_tweet.get_replicate_service")
async def test_create_video_tweet_blotato_error(
    mock_get_replicate, mock_get_blotato, mcp_client
):
    """Blotato error after successful video gen surfaces as ToolError with video_url."""
    mock_replicate = _mock_replicate_service()
    mock_get_replicate.return_value = mock_replicate

    mock_blotato = AsyncMock()
    mock_blotato.publish_post.side_effect = BlotatoAPIError(
        "Client error 401: Unauthorized", status_code=401
    )
    mock_get_blotato.return_value = mock_blotato

    result = await mcp_client.call_tool(
        "create_video_tweet",
        {
            "prompt": "A sunset",
            "tweet_text": "Beautiful",
            "image_url": "https://example.com/photo.jpg",
        },
        raise_on_error=False,
    )
    assert result.is_error is True
    assert "401" in result.content[0].text


@patch("content_automation.tools.video_tweet.get_blotato_service")
@patch("content_automation.tools.video_tweet.get_replicate_service")
async def test_create_video_tweet_uses_config_defaults(
    mock_get_replicate, mock_get_blotato, mcp_client
):
    """Without optional params, create_prediction uses config defaults."""
    mock_replicate = _mock_replicate_service()
    mock_get_replicate.return_value = mock_replicate
    mock_get_blotato.return_value = _mock_blotato_service(
        publish_return={"postSubmissionId": "sub-456"},
    )

    await mcp_client.call_tool(
        "create_video_tweet",
        {
            "prompt": "A sunset",
            "tweet_text": "Beautiful",
            "image_url": "https://example.com/photo.jpg",
        },
    )

    mock_replicate.create_prediction.assert_called_once()
    call_kwargs = mock_replicate.create_prediction.call_args
    # Config defaults: 81 frames, 720p, 24 fps
    assert call_kwargs.kwargs.get("num_frames", call_kwargs[1].get("num_frames", None)) == 81 or \
        (len(call_kwargs.args) > 2 and call_kwargs.args[2] == 81)


@patch("content_automation.tools.video_tweet.get_blotato_service")
@patch("content_automation.tools.video_tweet.get_replicate_service")
async def test_create_video_tweet_output_list_handling(
    mock_get_replicate, mock_get_blotato, mcp_client
):
    """When Replicate output is a list, extract first URL."""
    mock_replicate = _mock_replicate_service(
        poll_return={
            "status": "succeeded",
            "output": ["https://replicate.delivery/video.mp4"],
        }
    )
    mock_get_replicate.return_value = mock_replicate
    mock_get_blotato.return_value = _mock_blotato_service(
        publish_return={"postSubmissionId": "sub-456"},
        poll_return={
            "status": "published",
            "publicUrl": "https://twitter.com/status/789",
        },
    )

    result = await mcp_client.call_tool(
        "create_video_tweet",
        {
            "prompt": "A sunset",
            "tweet_text": "Beautiful",
            "image_url": "https://example.com/photo.jpg",
        },
    )
    data = json.loads(result.content[0].text)
    assert data["video_url"] == "https://replicate.delivery/video.mp4"


@patch("content_automation.tools.video_tweet.get_blotato_service")
@patch("content_automation.tools.video_tweet.get_replicate_service")
async def test_create_video_tweet_progress_reports(
    mock_get_replicate, mock_get_blotato, mcp_client
):
    """Pipeline completes without error when progress reporting is active."""
    mock_replicate = _mock_replicate_service()
    mock_get_replicate.return_value = mock_replicate
    mock_get_blotato.return_value = _mock_blotato_service(
        publish_return={"postSubmissionId": "sub-456"},
    )

    # Just verify pipeline completes without error -- progress reporting
    # is implicit via ctx.report_progress calls within the tool
    result = await mcp_client.call_tool(
        "create_video_tweet",
        {
            "prompt": "A sunset",
            "tweet_text": "Beautiful",
            "image_url": "https://example.com/photo.jpg",
        },
    )
    assert result.is_error is not True
