"""Unit tests for ServerConfig defaults and validation."""

from content_automation.config import get_settings


def test_video_config_defaults():
    """New video generation fields have correct defaults."""
    settings = get_settings()

    assert settings.default_video_resolution == "720p"
    assert settings.default_video_frames == 81
    assert settings.default_video_fps == 24
    assert settings.video_generation_timeout == 300.0


def test_old_video_fields_removed():
    """Obsolete default_video_model and default_video_duration are gone."""
    settings = get_settings()

    assert not hasattr(settings, "default_video_model")
    assert not hasattr(settings, "default_video_duration")


def test_resilience_config_defaults():
    """Resilience fields have correct defaults."""
    settings = get_settings()

    assert settings.replicate_daily_budget == 50
    assert settings.circuit_breaker_threshold == 5
    assert settings.circuit_breaker_recovery_seconds == 60.0
    assert settings.blotato_rpm_limit == 30
    assert settings.twitter_daily_post_limit == 100
