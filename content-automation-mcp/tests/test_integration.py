"""Integration tests: full MCP tool flow via FastMCP in-process Client with respx HTTP mocking.

These tests exercise the real code path: client -> tool -> service -> httpx (mocked by respx).
No unittest.mock patches -- respx intercepts actual httpx requests at the transport layer.
"""

import json

import httpx
import pytest
import respx

from content_automation.services.blotato import BlotatoService
from content_automation.services.replicate import ReplicateService


# ---------------------------------------------------------------------------
# Helpers: real service instances (no singleton cache) wired into tools
# ---------------------------------------------------------------------------


def _fresh_blotato() -> BlotatoService:
    return BlotatoService(api_key="test-key", account_id="test-account")


def _fresh_replicate() -> ReplicateService:
    return ReplicateService(api_token="test-token")


# ---------------------------------------------------------------------------
# create_tweet integration
# ---------------------------------------------------------------------------


@respx.mock
async def test_integration_create_tweet_success(mcp_client, monkeypatch):
    """Full round-trip: client.call_tool -> tweet tool -> BlotatoService -> httpx (mocked)."""
    monkeypatch.setattr(
        "content_automation.tools.tweet.get_blotato_service", _fresh_blotato
    )

    # Mock Blotato publish endpoint
    respx.post("https://backend.blotato.com/v2/posts").mock(
        return_value=httpx.Response(200, json={"postSubmissionId": "int-sub-001"})
    )
    # Mock Blotato poll endpoint
    respx.get("https://backend.blotato.com/v2/posts/int-sub-001").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "published",
                "publicUrl": "https://twitter.com/user/status/999",
            },
        )
    )

    result = await mcp_client.call_tool("create_tweet", {"text": "Integration test tweet"})
    data = json.loads(result.content[0].text)

    assert data["postSubmissionId"] == "int-sub-001"
    assert data["publicUrl"] == "https://twitter.com/user/status/999"
    assert data["status"] == "published"


@respx.mock
async def test_integration_create_tweet_server_error(mcp_client, monkeypatch):
    """Blotato 500 errors propagate as ToolError through the full stack."""
    monkeypatch.setattr(
        "content_automation.tools.tweet.get_blotato_service", _fresh_blotato
    )

    respx.post("https://backend.blotato.com/v2/posts").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )

    result = await mcp_client.call_tool(
        "create_tweet", {"text": "Should fail"}, raise_on_error=False
    )
    assert result.is_error is True
    assert "500" in result.content[0].text


@respx.mock
async def test_integration_create_tweet_with_media(mcp_client, monkeypatch):
    """Media URLs flow through the full stack to Blotato's httpx request."""
    monkeypatch.setattr(
        "content_automation.tools.tweet.get_blotato_service", _fresh_blotato
    )

    post_route = respx.post("https://backend.blotato.com/v2/posts").mock(
        return_value=httpx.Response(200, json={"postSubmissionId": "int-sub-002"})
    )
    respx.get("https://backend.blotato.com/v2/posts/int-sub-002").mock(
        return_value=httpx.Response(
            200, json={"status": "published", "publicUrl": "https://twitter.com/status/888"}
        )
    )

    await mcp_client.call_tool(
        "create_tweet",
        {"text": "With media", "media_urls": ["https://example.com/img.png"]},
    )

    # Verify the actual HTTP body sent to Blotato
    sent_body = json.loads(post_route.calls.last.request.content)
    assert sent_body["post"]["content"]["mediaUrls"] == ["https://example.com/img.png"]


# ---------------------------------------------------------------------------
# create_video_tweet integration
# ---------------------------------------------------------------------------


@respx.mock
async def test_integration_create_video_tweet_success(mcp_client, monkeypatch):
    """Full pipeline: client -> video_tweet tool -> Replicate + Blotato services -> httpx."""
    monkeypatch.setattr(
        "content_automation.tools.video_tweet.get_replicate_service", _fresh_replicate
    )
    monkeypatch.setattr(
        "content_automation.tools.video_tweet.get_blotato_service", _fresh_blotato
    )

    # Replicate: create prediction
    respx.post(
        "https://api.replicate.com/v1/models/wan-video/wan-2.2-i2v-fast/predictions"
    ).mock(
        return_value=httpx.Response(
            201, json={"id": "int-pred-001", "status": "starting"}
        )
    )

    # Replicate: poll prediction (return succeeded immediately)
    respx.get("https://api.replicate.com/v1/predictions/int-pred-001").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "int-pred-001",
                "status": "succeeded",
                "output": "https://replicate.delivery/int-video.mp4",
            },
        )
    )

    # Blotato: publish post with video
    respx.post("https://backend.blotato.com/v2/posts").mock(
        return_value=httpx.Response(200, json={"postSubmissionId": "int-sub-vid-001"})
    )
    respx.get("https://backend.blotato.com/v2/posts/int-sub-vid-001").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "published",
                "publicUrl": "https://twitter.com/status/video-777",
            },
        )
    )

    result = await mcp_client.call_tool(
        "create_video_tweet",
        {
            "prompt": "Ocean waves crashing on rocks",
            "tweet_text": "Nature is beautiful",
            "image_url": "https://example.com/ocean.jpg",
        },
    )
    data = json.loads(result.content[0].text)

    assert data["prediction_id"] == "int-pred-001"
    assert data["video_url"] == "https://replicate.delivery/int-video.mp4"
    assert data["postSubmissionId"] == "int-sub-vid-001"
    assert data["publicUrl"] == "https://twitter.com/status/video-777"
    assert data["status"] == "published"


@respx.mock
async def test_integration_create_video_tweet_replicate_error(mcp_client, monkeypatch):
    """Replicate 422 error propagates as ToolError through the full stack."""
    monkeypatch.setattr(
        "content_automation.tools.video_tweet.get_replicate_service", _fresh_replicate
    )
    monkeypatch.setattr(
        "content_automation.tools.video_tweet.get_blotato_service", _fresh_blotato
    )

    respx.post(
        "https://api.replicate.com/v1/models/wan-video/wan-2.2-i2v-fast/predictions"
    ).mock(
        return_value=httpx.Response(422, text="Invalid input parameters")
    )

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
    assert "422" in result.content[0].text


@respx.mock
async def test_integration_video_tweet_blotato_fails_after_generation(
    mcp_client, monkeypatch
):
    """When Blotato fails after video generation, error includes the video URL."""
    monkeypatch.setattr(
        "content_automation.tools.video_tweet.get_replicate_service", _fresh_replicate
    )
    monkeypatch.setattr(
        "content_automation.tools.video_tweet.get_blotato_service", _fresh_blotato
    )

    # Replicate succeeds
    respx.post(
        "https://api.replicate.com/v1/models/wan-video/wan-2.2-i2v-fast/predictions"
    ).mock(
        return_value=httpx.Response(
            201, json={"id": "int-pred-002", "status": "starting"}
        )
    )
    respx.get("https://api.replicate.com/v1/predictions/int-pred-002").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "succeeded",
                "output": "https://replicate.delivery/vid2.mp4",
            },
        )
    )

    # Blotato fails
    respx.post("https://backend.blotato.com/v2/posts").mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )

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
    # Error message should include the video URL so the user can recover it
    assert "replicate.delivery" in result.content[0].text
