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

    # Optional with defaults
    default_video_model: str = Field(
        default="wan-2.1", description="Default Replicate video model"
    )
    default_video_duration: int = Field(
        default=5, description="Default video duration in seconds"
    )
    dry_run: bool = Field(
        default=False, description="Skip actual API calls, log what would be sent"
    )
    log_level: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)")

    model_config = {"env_prefix": "", "env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> ServerConfig:
    """Cached settings instance. Raises ValidationError on missing required env vars."""
    return ServerConfig()
