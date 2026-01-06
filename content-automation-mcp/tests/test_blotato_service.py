"""Unit tests for BlotatoService with mocked HTTP via respx."""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from content_automation.services.blotato import BlotatoAPIError, BlotatoService

API_KEY = "test-blotato-key"
ACCOUNT_ID = "acct-12345"
BASE_URL = "https://backend.blotato.com/v2"


@pytest.fixture
def service():
    return BlotatoService(api_key=API_KEY, account_id=ACCOUNT_ID)


# --- publish_post tests ---


@respx.mock
async def test_publish_text_only(service: BlotatoService):
    """publish_post with text only sends correct body and returns response."""
    route = respx.post(f"{BASE_URL}/posts").mock(
        return_value=httpx.Response(200, json={"postSubmissionId": "uuid-123"})
    )

    result = await service.publish_post(text="hello")

    assert result == {"postSubmissionId": "uuid-123"}
    assert route.called
    req_body = route.calls[0].request.content
    import json

    body = json.loads(req_body)
    assert body["post"]["content"]["text"] == "hello"
    assert body["post"]["content"]["mediaUrls"] == []


@respx.mock
async def test_publish_with_media(service: BlotatoService):
    """publish_post includes mediaUrls when provided."""
    route = respx.post(f"{BASE_URL}/posts").mock(
        return_value=httpx.Response(200, json={"postSubmissionId": "uuid-456"})
    )

    result = await service.publish_post(
        text="hi", media_urls=["https://example.com/img.jpg"]
    )

    assert result == {"postSubmissionId": "uuid-456"}
    import json

    body = json.loads(route.calls[0].request.content)
    assert body["post"]["content"]["mediaUrls"] == ["https://example.com/img.jpg"]


@respx.mock
async def test_auth_header(service: BlotatoService):
    """Every request uses blotato-api-key header, not Authorization Bearer."""
    route = respx.post(f"{BASE_URL}/posts").mock(
        return_value=httpx.Response(200, json={"postSubmissionId": "uuid-789"})
    )

    await service.publish_post(text="auth test")

    request = route.calls[0].request
    assert request.headers["blotato-api-key"] == API_KEY
    assert "authorization" not in request.headers


@respx.mock
async def test_account_id(service: BlotatoService):
    """Request body includes configured account ID."""
    route = respx.post(f"{BASE_URL}/posts").mock(
        return_value=httpx.Response(200, json={"postSubmissionId": "uuid-acc"})
    )

    await service.publish_post(text="account test")

    import json

    body = json.loads(route.calls[0].request.content)
    assert body["post"]["accountId"] == ACCOUNT_ID


@respx.mock
async def test_thread(service: BlotatoService):
    """publish_post includes additionalPosts for thread creation."""
    route = respx.post(f"{BASE_URL}/posts").mock(
        return_value=httpx.Response(200, json={"postSubmissionId": "uuid-thread"})
    )

    additional = [
        {"text": "2/3", "mediaUrls": []},
        {"text": "3/3", "mediaUrls": []},
    ]
    await service.publish_post(text="1/3", additional_posts=additional)

    import json

    body = json.loads(route.calls[0].request.content)
    assert body["post"]["content"]["additionalPosts"] == additional


@respx.mock
async def test_platform_fields(service: BlotatoService):
    """Both content.platform and target.targetType are 'twitter'."""
    route = respx.post(f"{BASE_URL}/posts").mock(
        return_value=httpx.Response(200, json={"postSubmissionId": "uuid-plat"})
    )

    await service.publish_post(text="platform test")

    import json

    body = json.loads(route.calls[0].request.content)
    assert body["post"]["content"]["platform"] == "twitter"
    assert body["post"]["target"]["targetType"] == "twitter"


# --- retry tests ---


@respx.mock
async def test_retry_on_5xx(service: BlotatoService):
    """500 responses are retried up to 3 times; raises BlotatoAPIError if all fail."""
    respx.post(f"{BASE_URL}/posts").mock(
        return_value=httpx.Response(500, json={"error": "server error"})
    )

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(BlotatoAPIError) as exc_info:
            await service.publish_post(text="retry test")

    assert exc_info.value.status_code == 500


@respx.mock
async def test_retry_on_timeout(service: BlotatoService):
    """Timeout triggers retry with backoff."""
    respx.post(f"{BASE_URL}/posts").mock(side_effect=httpx.TimeoutException("timed out"))

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(BlotatoAPIError):
            await service.publish_post(text="timeout test")


@respx.mock
async def test_no_retry_on_4xx(service: BlotatoService):
    """4xx responses raise BlotatoAPIError immediately (no retry)."""
    route = respx.post(f"{BASE_URL}/posts").mock(
        return_value=httpx.Response(400, json={"error": "bad request"})
    )

    with pytest.raises(BlotatoAPIError) as exc_info:
        await service.publish_post(text="bad request test")

    assert exc_info.value.status_code == 400
    # Should only be called once -- no retries on 4xx
    assert route.call_count == 1


# --- poll_post_status tests ---


@respx.mock
async def test_poll_post_status_published(service: BlotatoService):
    """poll_post_status returns data when status is 'published'."""
    respx.get(f"{BASE_URL}/posts/sub-123").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "published",
                "publicUrl": "https://twitter.com/user/status/999",
            },
        )
    )

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await service.poll_post_status("sub-123")

    assert result["status"] == "published"
    assert result["publicUrl"] == "https://twitter.com/user/status/999"


@respx.mock
async def test_poll_post_status_failed(service: BlotatoService):
    """poll_post_status raises BlotatoAPIError when status is 'failed'."""
    respx.get(f"{BASE_URL}/posts/sub-fail").mock(
        return_value=httpx.Response(
            200,
            json={"status": "failed", "errorMessage": "Duplicate content detected"},
        )
    )

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(BlotatoAPIError, match="Duplicate content detected"):
            await service.poll_post_status("sub-fail")
