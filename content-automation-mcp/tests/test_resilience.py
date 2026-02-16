"""Unit tests for resilience primitives: CircuitBreaker, CostBudget, RateLimiter."""

from unittest.mock import patch

import pytest

from content_automation.resilience import (
    BudgetExceededError,
    CircuitBreaker,
    CircuitOpenError,
    CostBudget,
    RateLimiter,
    RateLimitError,
    ResilienceError,
)


# --- Exception hierarchy ---


def test_all_errors_subclass_resilience_error():
    assert issubclass(CircuitOpenError, ResilienceError)
    assert issubclass(BudgetExceededError, ResilienceError)
    assert issubclass(RateLimitError, ResilienceError)


# --- CircuitBreaker ---


class TestCircuitBreaker:
    def test_starts_closed_allows_calls(self):
        cb = CircuitBreaker("test-service", threshold=3)
        cb.check()  # should not raise

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker("test-service", threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.check()  # still closed at 2 failures
        cb.record_failure()  # 3rd failure -> opens
        with pytest.raises(CircuitOpenError, match="test-service"):
            cb.check()

    def test_open_error_includes_service_name(self):
        cb = CircuitBreaker("replicate", threshold=1)
        cb.record_failure()
        with pytest.raises(CircuitOpenError) as exc_info:
            cb.check()
        assert "replicate" in str(exc_info.value)

    @patch("content_automation.resilience.time.monotonic")
    def test_resets_to_half_open_after_recovery(self, mock_time):
        mock_time.return_value = 0.0
        cb = CircuitBreaker("svc", threshold=2, recovery_seconds=10.0)
        cb.record_failure()
        cb.record_failure()

        # Still open at t=5
        mock_time.return_value = 5.0
        with pytest.raises(CircuitOpenError):
            cb.check()

        # Half-open at t=11 -- allows one probe
        mock_time.return_value = 11.0
        cb.check()  # should not raise (half-open probe)

    @patch("content_automation.resilience.time.monotonic")
    def test_closes_after_successful_probe(self, mock_time):
        mock_time.return_value = 0.0
        cb = CircuitBreaker("svc", threshold=1, recovery_seconds=5.0)
        cb.record_failure()

        mock_time.return_value = 6.0
        cb.check()  # half-open probe allowed
        cb.record_success()  # closes circuit

        cb.check()  # should not raise -- circuit is closed now

    @patch("content_automation.resilience.time.monotonic")
    def test_reopens_if_probe_fails(self, mock_time):
        mock_time.return_value = 0.0
        cb = CircuitBreaker("svc", threshold=1, recovery_seconds=5.0)
        cb.record_failure()

        mock_time.return_value = 6.0
        cb.check()  # half-open probe
        cb.record_failure()  # probe failed -> back to open

        mock_time.return_value = 7.0
        with pytest.raises(CircuitOpenError):
            cb.check()

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker("svc", threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        cb.check()  # should not raise -- counter reset after success


# --- CostBudget ---


class TestCostBudget:
    def test_starts_at_zero(self):
        budget = CostBudget(daily_limit=5)
        assert budget.remaining == 5

    def test_increments_on_usage(self):
        budget = CostBudget(daily_limit=10)
        budget.record_usage()
        assert budget.remaining == 9

    def test_raises_when_budget_exceeded(self):
        budget = CostBudget(daily_limit=2)
        budget.record_usage()
        budget.record_usage()
        with pytest.raises(BudgetExceededError):
            budget.check()

    def test_allows_when_under_budget(self):
        budget = CostBudget(daily_limit=3)
        budget.record_usage()
        budget.check()  # should not raise

    def test_reset_clears_counter(self):
        budget = CostBudget(daily_limit=2)
        budget.record_usage()
        budget.record_usage()
        budget.reset()
        assert budget.remaining == 2
        budget.check()  # should not raise

    def test_remaining_property(self):
        budget = CostBudget(daily_limit=10)
        budget.record_usage()
        budget.record_usage()
        budget.record_usage()
        assert budget.remaining == 7


# --- RateLimiter ---


class TestRateLimiter:
    @patch("content_automation.resilience.time.monotonic")
    def test_allows_requests_under_limit(self, mock_time):
        mock_time.return_value = 0.0
        rl = RateLimiter(rpm_limit=3, daily_limit=100)
        rl.record()
        rl.record()
        rl.check()  # should not raise

    @patch("content_automation.resilience.time.monotonic")
    def test_raises_when_rpm_exceeded(self, mock_time):
        mock_time.return_value = 0.0
        rl = RateLimiter(rpm_limit=2, daily_limit=100)
        rl.record()
        rl.record()
        with pytest.raises(RateLimitError, match="per-minute"):
            rl.check()

    @patch("content_automation.resilience.time.monotonic")
    def test_old_entries_expire_from_minute_window(self, mock_time):
        mock_time.return_value = 0.0
        rl = RateLimiter(rpm_limit=2, daily_limit=100)
        rl.record()
        rl.record()

        # 61 seconds later, old entries should be pruned
        mock_time.return_value = 61.0
        rl.check()  # should not raise

    @patch("content_automation.resilience.time.monotonic")
    def test_raises_when_daily_limit_exceeded(self, mock_time):
        mock_time.return_value = 0.0
        rl = RateLimiter(rpm_limit=1000, daily_limit=3)
        # Space records across minutes to avoid rpm limit
        for i in range(3):
            mock_time.return_value = i * 61.0
            rl.record()

        mock_time.return_value = 200.0
        with pytest.raises(RateLimitError, match="daily"):
            rl.check()

    @patch("content_automation.resilience.time.monotonic")
    def test_daily_entries_expire_after_24h(self, mock_time):
        mock_time.return_value = 0.0
        rl = RateLimiter(rpm_limit=1000, daily_limit=2)
        rl.record()
        rl.record()

        # 24h + 1s later
        mock_time.return_value = 86401.0
        rl.check()  # should not raise
