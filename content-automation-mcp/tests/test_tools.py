"""Tool-specific tests: service integration, validation errors, media and threading."""

import json
from unittest.mock import AsyncMock, patch

from content_automation.services.blotato import BlotatoAPIError

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


async def test_create_video_tweet_stub(mcp_client):
    """Calling create_video_tweet with valid args returns a STUB response."""
    result = await mcp_client.call_tool(
        "create_video_tweet",
        {"prompt": "A sunset over the ocean", "tweet_text": "Beautiful sunset"},
    )
    text = result.content[0].text
    assert "STUB" in text


async def test_create_video_tweet_empty_prompt_error(mcp_client):
    """Empty video prompt produces an isError=True result."""
    result = await mcp_client.call_tool(
        "create_video_tweet",
        {"prompt": "", "tweet_text": "Some text"},
        raise_on_error=False,
    )
    assert result.is_error is True


async def test_create_video_tweet_empty_tweet_text_error(mcp_client):
    """Empty tweet_text in create_video_tweet produces an isError=True result."""
    result = await mcp_client.call_tool(
        "create_video_tweet",
        {"prompt": "A valid prompt", "tweet_text": ""},
        raise_on_error=False,
    )
    assert result.is_error is True
