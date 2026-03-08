"""Resilience primitives: circuit breaker, cost budget, rate limiter.

Standalone, synchronous guards designed to be called before async service
requests. Each exposes a check()/record pattern:
  - check() raises if the guard would reject the request
  - record_success/record_failure/record_usage/record() tracks outcomes

Plan 04-02 wires these into the service layer.
"""

from __future__ import annotations

import enum
import time
from collections import deque


class ResilienceError(Exception):
    """Base exception for all resilience guard rejections."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class CircuitOpenError(ResilienceError):
    """Raised when circuit breaker is open and rejecting requests."""


class BudgetExceededError(ResilienceError):
    """Raised when daily cost budget has been exhausted."""


class RateLimitError(ResilienceError):
    """Raised when request rate exceeds the configured limit."""


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------


class _State(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Per-service circuit breaker with closed/open/half-open states.

    Args:
        service_name: Identifier for the protected service (used in error messages).
        threshold: Consecutive failures before the circuit opens.
        recovery_seconds: Seconds to wait before allowing a half-open probe.
    """

    def __init__(
        self,
        service_name: str,
        threshold: int = 5,
        recovery_seconds: float = 60.0,
    ):
        self._service_name = service_name
        self._threshold = threshold
        self._recovery_seconds = recovery_seconds
        self._state = _State.CLOSED
        self._failure_count = 0
        self._opened_at: float = 0.0

    def check(self) -> None:
        """Allow request or raise CircuitOpenError."""
        if self._state is _State.CLOSED:
            return

        if self._state is _State.OPEN:
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self._recovery_seconds:
                self._state = _State.HALF_OPEN
                return  # allow probe
            raise CircuitOpenError(
                f"Circuit open for {self._service_name} "
                f"({self._recovery_seconds - elapsed:.0f}s until probe)"
            )

        # HALF_OPEN: already allowed one probe, reject further until resolved
        raise CircuitOpenError(
            f"Circuit half-open for {self._service_name}, probe in progress"
        )

    def record_success(self) -> None:
        """Reset failure count and close circuit."""
        self._failure_count = 0
        self._state = _State.CLOSED

    def record_failure(self) -> None:
        """Increment failure count; open circuit if threshold reached."""
        self._failure_count += 1
        if self._failure_count >= self._threshold:
            self._state = _State.OPEN
            self._opened_at = time.monotonic()


# ---------------------------------------------------------------------------
# CostBudget
# ---------------------------------------------------------------------------


class CostBudget:
    """Daily generation cost counter.

    Args:
        daily_limit: Maximum allowed usages per day.
    """

    def __init__(self, daily_limit: int = 50):
        self._daily_limit = daily_limit
        self._count = 0

    def check(self) -> None:
        """Allow usage or raise BudgetExceededError."""
        if self._count >= self._daily_limit:
            raise BudgetExceededError(
                f"Daily budget exhausted ({self._count}/{self._daily_limit})"
            )

    def record_usage(self) -> None:
        """Increment the usage counter."""
        self._count += 1

    def reset(self) -> None:
        """Reset counter to zero (for daily reset)."""
        self._count = 0

    @property
    def remaining(self) -> int:
        """Number of usages remaining before budget is exceeded."""
        return self._daily_limit - self._count


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """Sliding-window rate limiter with per-minute and per-day windows.

    Args:
        rpm_limit: Maximum requests per 60-second window.
        daily_limit: Maximum requests per 86400-second window.
    """

    _MINUTE = 60.0
    _DAY = 86400.0

    def __init__(self, rpm_limit: int = 30, daily_limit: int = 100):
        self._rpm_limit = rpm_limit
        self._daily_limit = daily_limit
        self._timestamps: deque[float] = deque()

    def check(self) -> None:
        """Allow request or raise RateLimitError."""
        now = time.monotonic()
        self._prune(now)

        minute_count = sum(1 for ts in self._timestamps if now - ts < self._MINUTE)
        if minute_count >= self._rpm_limit:
            raise RateLimitError(
                f"per-minute rate limit exceeded ({minute_count}/{self._rpm_limit})"
            )

        if len(self._timestamps) >= self._daily_limit:
            raise RateLimitError(
                f"daily rate limit exceeded ({len(self._timestamps)}/{self._daily_limit})"
            )

    def record(self) -> None:
        """Record a request timestamp."""
        self._timestamps.append(time.monotonic())

    def _prune(self, now: float) -> None:
        """Remove entries older than the daily window."""
        while self._timestamps and (now - self._timestamps[0]) >= self._DAY:
            self._timestamps.popleft()
