"""Server configuration via environment variables with pydantic-settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class ServerConfig(BaseSettings):
    """Configuration loaded from environment variables.

    Required fields must be set or the server will fail at startup
    with a clear ValidationError listing the missing values.
    """

    # Required -- server will not start without these
    replicate_api_token: str = Field(description="Replicate API token for video generation")
    blotato_api_key: str = Field(description="Blotato API key for tweet posting")
    blotato_account_id: str = Field(description="Target Twitter account ID in Blotato")

    # Video generation defaults
    default_video_resolution: str = Field(
        default="720p", description="Default video resolution (480p or 720p)"
    )
    default_video_frames: int = Field(
        default=81, description="Default number of frames (81-100)"
    )
    default_video_fps: int = Field(
        default=24, description="Default frames per second (5-24)"
    )
    video_generation_timeout: float = Field(
        default=300.0, description="Max seconds to wait for video generation"
    )
    dry_run: bool = Field(
        default=False, description="Skip actual API calls, log what would be sent"
    )
    log_level: str = Field(
        default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )

    # Resilience settings
    replicate_daily_budget: int = Field(
        default=50, description="Max Replicate generations per day"
    )
    circuit_breaker_threshold: int = Field(
        default=5, description="Consecutive failures before circuit opens"
    )
    circuit_breaker_recovery_seconds: float = Field(
        default=60.0, description="Seconds before circuit breaker resets to half-open"
    )
    blotato_rpm_limit: int = Field(
        default=30, description="Max Blotato requests per minute"
    )
    twitter_daily_post_limit: int = Field(
        default=100, description="Max Twitter posts per day"
    )

    # Transport settings
    mcp_transport: str = Field(
        default="stdio", description="MCP transport: 'stdio' (default) or 'http'"
    )
    mcp_http_port: int = Field(
        default=8000, description="HTTP port when using streamable HTTP transport"
    )

    model_config = {"env_prefix": "", "env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> ServerConfig:
    """Cached settings instance. Raises ValidationError on missing required env vars."""
    return ServerConfig()
