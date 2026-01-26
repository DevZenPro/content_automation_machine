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
