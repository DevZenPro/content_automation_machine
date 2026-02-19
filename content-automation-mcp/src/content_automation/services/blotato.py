"""Blotato API service for posting tweets via httpx.AsyncClient."""

from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx
import structlog

from content_automation.config import get_settings
from content_automation.resilience import CircuitBreaker, RateLimiter

logger = structlog.get_logger()


class BlotatoAPIError(Exception):
    """Raised when a Blotato API call fails."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class BlotatoService:
    """Blotato API client with retry logic and post status polling."""

    BASE_URL = "https://backend.blotato.com/v2"

    def __init__(
        self,
        api_key: str,
        account_id: str,
        circuit_breaker: CircuitBreaker | None = None,
        rate_limiter: RateLimiter | None = None,
    ):
        self._api_key = api_key
        self._account_id = account_id
        self._circuit_breaker = circuit_breaker
        self._rate_limiter = rate_limiter
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "blotato-api-key": api_key,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def publish_post(
        self,
        text: str,
        media_urls: list[str] | None = None,
        additional_posts: list[dict[str, Any]] | None = None,
    ) -> dict:
        """Publish a post to Twitter via Blotato. Retries on transient failures."""
        body: dict[str, Any] = {
            "post": {
                "accountId": self._account_id,
                "content": {
                    "text": text,
                    "mediaUrls": media_urls or [],
                    "platform": "twitter",
                },
                "target": {
                    "targetType": "twitter",
                },
            }
        }
        if additional_posts:
            body["post"]["content"]["additionalPosts"] = additional_posts

        # Check rate limiter before making the API call
        if self._rate_limiter:
            self._rate_limiter.check()

        return await self._post_with_retry("/posts", body)

    async def _post_with_retry(
        self, path: str, body: dict, max_attempts: int = 3
    ) -> dict:
        """POST with retry on 5xx/timeout/connection errors. Raises immediately on 4xx."""
        # Check circuit breaker before attempting any requests
        if self._circuit_breaker:
            self._circuit_breaker.check()

        last_error: Exception | None = None

        for attempt in range(max_attempts):
            try:
                response = await self._client.post(path, json=body)

                if response.status_code >= 400 and response.status_code < 500:
                    raise BlotatoAPIError(
                        f"Client error {response.status_code}: {response.text}",
                        status_code=response.status_code,
                    )

                if response.status_code >= 500:
                    last_error = BlotatoAPIError(
                        f"Server error {response.status_code}: {response.text}",
                        status_code=response.status_code,
                    )
                else:
                    # Record success on both circuit breaker and rate limiter
                    if self._circuit_breaker:
                        self._circuit_breaker.record_success()
                    if self._rate_limiter:
                        self._rate_limiter.record()
                    return response.json()

            except BlotatoAPIError:
                raise
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_error = BlotatoAPIError(
                    f"Connection error: {exc}", status_code=None
                )

            if attempt < max_attempts - 1:
                delay = (2**attempt) + random.uniform(0, 1)
                logger.warning("blotato_retry", attempt=attempt + 1, delay=round(delay, 2))
                await asyncio.sleep(delay)

        # All retries exhausted -- record failure
        if self._circuit_breaker:
            self._circuit_breaker.record_failure()
        raise last_error  # type: ignore[misc]

    async def poll_post_status(
        self, submission_id: str, max_wait: float = 30.0
    ) -> dict:
        """Poll GET /posts/{id} until published or failed. Raises on timeout."""
        deadline = asyncio.get_event_loop().time() + max_wait

        while asyncio.get_event_loop().time() < deadline:
            response = await self._client.get(f"/posts/{submission_id}")
            response.raise_for_status()
            data = response.json()
            status = data.get("status")

            if status == "published":
                return data
            if status == "failed":
                raise BlotatoAPIError(
                    data.get("errorMessage", "Post failed"),
                    status_code=None,
                )

            await asyncio.sleep(2)

        raise BlotatoAPIError(
            f"Post {submission_id} did not complete within {max_wait}s",
            status_code=None,
        )

    async def close(self):
        """Close the underlying httpx client."""
        await self._client.aclose()


_service_instance: BlotatoService | None = None


def get_blotato_service() -> BlotatoService:
    """Factory that returns a cached BlotatoService instance."""
    global _service_instance
    if _service_instance is None:
        settings = get_settings()
        cb = CircuitBreaker(
            "blotato",
            settings.circuit_breaker_threshold,
            settings.circuit_breaker_recovery_seconds,
        )
        rl = RateLimiter(
            rpm_limit=settings.blotato_rpm_limit,
            daily_limit=settings.twitter_daily_post_limit,
        )
        _service_instance = BlotatoService(
            api_key=settings.blotato_api_key,
            account_id=settings.blotato_account_id,
            circuit_breaker=cb,
            rate_limiter=rl,
        )
    return _service_instance
