"""Replicate API service for video generation via httpx.AsyncClient."""

from __future__ import annotations

import asyncio

import httpx
import structlog

from content_automation.config import get_settings
from content_automation.resilience import CircuitBreaker, CostBudget

logger = structlog.get_logger()


class ReplicateAPIError(Exception):
    """Raised when a Replicate API call fails."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ReplicateService:
    """Replicate API client for video prediction creation and polling."""

    BASE_URL = "https://api.replicate.com/v1"
    MODEL_ENDPOINT = "/models/wan-video/wan-2.2-i2v-fast/predictions"

    def __init__(
        self,
        api_token: str,
        circuit_breaker: CircuitBreaker | None = None,
        cost_budget: CostBudget | None = None,
    ):
        self._api_token = api_token
        self._circuit_breaker = circuit_breaker
        self._cost_budget = cost_budget
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    @staticmethod
    def _normalize_image(image: str) -> str:
        """Ensure image input has proper format for Replicate API."""
        if image.startswith("http") or image.startswith("data:"):
            return image
        # Raw base64 -- add data URI prefix
        return f"data:image/png;base64,{image}"

    async def create_prediction(
        self,
        image: str,
        prompt: str,
        num_frames: int = 81,
        resolution: str = "720p",
        aspect_ratio: str = "16:9",
        frames_per_second: int = 24,
    ) -> dict:
        """Create an async video prediction. Returns prediction object with id and urls."""
        # Pre-flight resilience checks
        if self._circuit_breaker:
            self._circuit_breaker.check()
        if self._cost_budget:
            self._cost_budget.check()

        body = {
            "input": {
                "image": self._normalize_image(image),
                "prompt": prompt,
                "num_frames": num_frames,
                "resolution": resolution,
                "aspect_ratio": aspect_ratio,
                "frames_per_second": frames_per_second,
            }
        }

        logger.info(
            "replicate_create_prediction",
            prompt=prompt[:80],
            num_frames=num_frames,
            resolution=resolution,
        )

        response = await self._client.post(
            self.MODEL_ENDPOINT,
            json=body,
            headers={"Cancel-After": "5m"},
        )

        if response.status_code >= 500:
            if self._circuit_breaker:
                self._circuit_breaker.record_failure()
            raise ReplicateAPIError(
                f"Replicate API error {response.status_code}: {response.text}",
                status_code=response.status_code,
            )

        if response.status_code >= 400:
            raise ReplicateAPIError(
                f"Replicate API error {response.status_code}: {response.text}",
                status_code=response.status_code,
            )

        # Success -- record on both guards
        if self._circuit_breaker:
            self._circuit_breaker.record_success()
        if self._cost_budget:
            self._cost_budget.record_usage()

        return response.json()

    async def get_prediction(self, prediction_id: str) -> dict:
        """Get current prediction status."""
        if self._circuit_breaker:
            self._circuit_breaker.check()

        response = await self._client.get(f"/predictions/{prediction_id}")

        if response.status_code >= 500:
            if self._circuit_breaker:
                self._circuit_breaker.record_failure()
            raise ReplicateAPIError(
                f"Failed to get prediction {prediction_id}: {response.text}",
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            raise ReplicateAPIError(
                f"Failed to get prediction {prediction_id}: {response.text}",
                status_code=response.status_code,
            )

        if self._circuit_breaker:
            self._circuit_breaker.record_success()
        return response.json()

    async def cancel_prediction(self, prediction_id: str) -> None:
        """Cancel a running prediction."""
        logger.info("replicate_cancel_prediction", prediction_id=prediction_id)
        await self._client.post(f"/predictions/{prediction_id}/cancel")

    async def poll_prediction(
        self, prediction_id: str, timeout: float = 300.0
    ) -> dict:
        """Poll until succeeded/failed/canceled. Exponential backoff: 2s base, 1.5x, 30s cap."""
        deadline = asyncio.get_event_loop().time() + timeout
        delay = 2.0
        poll_count = 0

        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                await self.cancel_prediction(prediction_id)
                raise TimeoutError(
                    f"Video generation timed out after {timeout}s. "
                    f"Prediction {prediction_id} was cancelled. "
                    "Try a shorter video (fewer frames) or retry."
                )

            prediction = await self.get_prediction(prediction_id)
            status = prediction.get("status")
            poll_count += 1

            logger.debug(
                "replicate_poll",
                prediction_id=prediction_id,
                status=status,
                poll_count=poll_count,
            )

            if status == "succeeded":
                return prediction

            if status in ("failed", "canceled", "aborted"):
                error = prediction.get("error", "Unknown error")
                raise RuntimeError(
                    f"Video generation {status}: {error}. "
                    f"Prediction ID: {prediction_id}"
                )

            await asyncio.sleep(min(delay, remaining))
            delay = min(delay * 1.5, 30.0)

    async def close(self):
        """Close the underlying httpx client."""
        await self._client.aclose()


_service_instance: ReplicateService | None = None


def get_replicate_service() -> ReplicateService:
    """Factory that returns a cached ReplicateService instance."""
    global _service_instance
    if _service_instance is None:
        settings = get_settings()
        cb = CircuitBreaker(
            "replicate",
            settings.circuit_breaker_threshold,
            settings.circuit_breaker_recovery_seconds,
        )
        budget = CostBudget(daily_limit=settings.replicate_daily_budget)
        _service_instance = ReplicateService(
            api_token=settings.replicate_api_token,
            circuit_breaker=cb,
            cost_budget=budget,
        )
    return _service_instance
