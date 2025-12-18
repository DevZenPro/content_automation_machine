"""Shared fixtures for content-automation MCP test suite."""

import os

import pytest
from fastmcp import Client

# Set test env vars BEFORE any server import so pydantic-settings picks them up
os.environ.setdefault("REPLICATE_API_TOKEN", "test-token")
os.environ.setdefault("BLOTATO_API_KEY", "test-key")
os.environ.setdefault("BLOTATO_ACCOUNT_ID", "test-account")

from content_automation.config import get_settings  # noqa: E402
from content_automation.server import mcp  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Clear the lru_cache on get_settings between tests."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def mcp_client():
    """In-process MCP client connected to the server -- no network needed."""
    async with Client(mcp) as client:
        yield client
