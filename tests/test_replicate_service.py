"""Unit tests for ReplicateService with mocked HTTP via respx."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from content_automation.services.replicate import (
    ReplicateAPIError,
    ReplicateService,
    get_replicate_service,
)

API_TOKEN = "test-replicate-token"
BASE_URL = "https://api.replicate.com/v1"
MODEL_URL = f"{BASE_URL}/models/wan-video/wan-2.2-i2v-fast/predictions"

PREDICTION_RESPONSE = {
    "id": "pred-abc123",
    "status": "starting",
    "urls": {
        "get": f"{BASE_URL}/predictions/pred-abc123",
        "cancel": f"{BASE_URL}/predictions/pred-abc123/cancel",
    },
}


@pytest.fixture
def service():
    return ReplicateService(api_token=API_TOKEN)


# --- create_prediction tests ---


@respx.mock
async def test_create_prediction(service: ReplicateService):
    """create_prediction POSTs to model endpoint with correct headers and body."""
    route = respx.post(MODEL_URL).mock(
        return_value=httpx.Response(201, json=PREDICTION_RESPONSE)
    )

    result = await service.create_prediction(
        image="https://example.com/photo.jpg",
        prompt="A cat walking gracefully",
        num_frames=81,
        resolution="720p",
        aspect_ratio="16:9",
        frames_per_second=24,
    )

    assert result == PREDICTION_RESPONSE
    assert route.called

    request = route.calls[0].request
    assert request.headers["authorization"] == f"Bearer {API_TOKEN}"
    assert request.headers["cancel-after"] == "5m"

    body = json.loads(request.content)
    assert body["input"]["image"] == "https://example.com/photo.jpg"
    assert body["input"]["prompt"] == "A cat walking gracefully"
    assert body["input"]["num_frames"] == 81
    assert body["input"]["resolution"] == "720p"
    assert body["input"]["aspect_ratio"] == "16:9"
    assert body["input"]["frames_per_second"] == 24


# --- get_prediction tests ---


@respx.mock
async def test_get_prediction(service: ReplicateService):
    """get_prediction GETs the prediction status."""
    pred_data = {"id": "pred-abc123", "status": "processing"}
    respx.get(f"{BASE_URL}/predictions/pred-abc123").mock(
        return_value=httpx.Response(200, json=pred_data)
    )

    result = await service.get_prediction("pred-abc123")
    assert result == pred_data


# --- poll_prediction tests ---


@respx.mock
async def test_poll_success(service: ReplicateService):
    """poll_prediction returns prediction when status becomes succeeded."""
    succeeded = {
        "id": "pred-abc123",
        "status": "succeeded",
        "output": "https://replicate.delivery/output.mp4",
    }

    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(200, json={"id": "pred-abc123", "status": "processing"})
        return httpx.Response(200, json=succeeded)

    respx.get(f"{BASE_URL}/predictions/pred-abc123").mock(side_effect=side_effect)

    with patch("content_automation.services.replicate.asyncio.sleep", new_callable=AsyncMock):
        result = await service.poll_prediction("pred-abc123", timeout=60.0)

    assert result["status"] == "succeeded"
    assert result["output"] == "https://replicate.delivery/output.mp4"


@respx.mock
async def test_polling_backoff(service: ReplicateService):
    """Polling uses exponential backoff: 2s -> 3s -> 4.5s."""
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count <= 3:
            return httpx.Response(200, json={"id": "pred-1", "status": "processing"})
        return httpx.Response(200, json={"id": "pred-1", "status": "succeeded"})

    respx.get(f"{BASE_URL}/predictions/pred-1").mock(side_effect=side_effect)

    sleep_delays = []
    original_sleep = AsyncMock()

    async def capture_sleep(delay):
        sleep_delays.append(delay)

    with patch("content_automation.services.replicate.asyncio.sleep", side_effect=capture_sleep):
        await service.poll_prediction("pred-1", timeout=60.0)

    # Backoff: 2s, 3s (2*1.5), 4.5s (3*1.5) -- but capped by remaining time
    assert len(sleep_delays) == 3
    assert sleep_delays[0] == pytest.approx(2.0, abs=0.1)
    assert sleep_delays[1] == pytest.approx(3.0, abs=0.1)
    assert sleep_delays[2] == pytest.approx(4.5, abs=0.1)


@respx.mock
async def test_timeout_cancellation(service: ReplicateService):
    """Timeout raises TimeoutError and cancels the prediction."""
    respx.get(f"{BASE_URL}/predictions/pred-timeout").mock(
        return_value=httpx.Response(200, json={"id": "pred-timeout", "status": "processing"})
    )
    cancel_route = respx.post(f"{BASE_URL}/predictions/pred-timeout/cancel").mock(
        return_value=httpx.Response(204)
    )

    with patch("content_automation.services.replicate.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(TimeoutError, match="timed out"):
            await service.poll_prediction("pred-timeout", timeout=0.1)

    assert cancel_route.called


@respx.mock
async def test_failed_prediction(service: ReplicateService):
    """Failed prediction raises RuntimeError with error detail."""
    respx.get(f"{BASE_URL}/predictions/pred-fail").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "pred-fail",
                "status": "failed",
                "error": "NSFW content detected",
            },
        )
    )

    with patch("content_automation.services.replicate.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(RuntimeError, match="NSFW content detected"):
            await service.poll_prediction("pred-fail", timeout=60.0)


# --- image input normalization tests ---


@respx.mock
async def test_image_url_passthrough(service: ReplicateService):
    """HTTP URLs are passed through as-is."""
    route = respx.post(MODEL_URL).mock(
        return_value=httpx.Response(201, json=PREDICTION_RESPONSE)
    )

    await service.create_prediction(
        image="https://example.com/photo.jpg", prompt="test"
    )

    body = json.loads(route.calls[0].request.content)
    assert body["input"]["image"] == "https://example.com/photo.jpg"


@respx.mock
async def test_data_uri_passthrough(service: ReplicateService):
    """Data URIs are passed through as-is."""
    data_uri = "data:image/png;base64,iVBORw0KGgoAAAANS"
    route = respx.post(MODEL_URL).mock(
        return_value=httpx.Response(201, json=PREDICTION_RESPONSE)
    )

    await service.create_prediction(image=data_uri, prompt="test")

    body = json.loads(route.calls[0].request.content)
    assert body["input"]["image"] == data_uri


@respx.mock
async def test_raw_base64_gets_prefix(service: ReplicateService):
    """Raw base64 (no data: prefix) gets data URI prefix prepended."""
    raw_b64 = "iVBORw0KGgoAAAANS"
    route = respx.post(MODEL_URL).mock(
        return_value=httpx.Response(201, json=PREDICTION_RESPONSE)
    )

    await service.create_prediction(image=raw_b64, prompt="test")

    body = json.loads(route.calls[0].request.content)
    assert body["input"]["image"] == f"data:image/png;base64,{raw_b64}"


# --- error handling tests ---


@respx.mock
async def test_create_prediction_api_error(service: ReplicateService):
    """Non-2xx response raises ReplicateAPIError."""
    respx.post(MODEL_URL).mock(
        return_value=httpx.Response(422, json={"detail": "Invalid input"})
    )

    with pytest.raises(ReplicateAPIError) as exc_info:
        await service.create_prediction(image="bad", prompt="test")

    assert exc_info.value.status_code == 422


# --- factory tests ---


def test_get_replicate_service():
    """get_replicate_service returns a cached ReplicateService instance."""
    # Reset module-level cache
    import content_automation.services.replicate as mod

    mod._service_instance = None

    svc = get_replicate_service()
    assert isinstance(svc, ReplicateService)

    svc2 = get_replicate_service()
    assert svc is svc2

    # Clean up
    mod._service_instance = None
