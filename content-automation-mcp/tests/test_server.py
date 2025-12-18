"""Server-level tests: tool discovery, config validation, stderr-only output."""

import os
import subprocess
import sys

import pytest
from pydantic import ValidationError

from content_automation.config import ServerConfig, get_settings


async def test_tool_discovery(mcp_client):
    """Server exposes both create_tweet and create_video_tweet tools."""
    tools = await mcp_client.list_tools()
    tool_names = {t.name for t in tools}
    assert "create_tweet" in tool_names
    assert "create_video_tweet" in tool_names


async def test_tool_schemas_have_descriptions(mcp_client):
    """Every registered tool has a non-empty description."""
    tools = await mcp_client.list_tools()
    for tool in tools:
        assert tool.description, f"Tool {tool.name} has no description"


def test_config_missing_env_vars(monkeypatch):
    """ServerConfig raises ValidationError when required env vars are missing."""
    get_settings.cache_clear()
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
    monkeypatch.delenv("BLOTATO_API_KEY", raising=False)
    monkeypatch.delenv("BLOTATO_ACCOUNT_ID", raising=False)
    with pytest.raises(ValidationError):
        ServerConfig()


def test_config_valid_env_vars(monkeypatch):
    """ServerConfig succeeds with all required env vars and values match."""
    monkeypatch.setenv("REPLICATE_API_TOKEN", "tok-abc")
    monkeypatch.setenv("BLOTATO_API_KEY", "key-xyz")
    monkeypatch.setenv("BLOTATO_ACCOUNT_ID", "acct-123")
    get_settings.cache_clear()
    cfg = ServerConfig()
    assert cfg.replicate_api_token == "tok-abc"
    assert cfg.blotato_api_key == "key-xyz"
    assert cfg.blotato_account_id == "acct-123"
    # Defaults
    assert cfg.default_video_model == "wan-2.1"
    assert cfg.dry_run is False


def test_stderr_only():
    """Importing the server module produces zero bytes on stdout."""
    env = os.environ.copy()
    env["REPLICATE_API_TOKEN"] = "test-token"
    env["BLOTATO_API_KEY"] = "test-key"
    env["BLOTATO_ACCOUNT_ID"] = "test-account"
    result = subprocess.run(
        [sys.executable, "-c", "import content_automation.server"],
        capture_output=True,
        env=env,
        cwd=os.path.join(os.path.dirname(__file__), ".."),
        timeout=10,
    )
    assert result.stdout == b"", f"Unexpected stdout: {result.stdout!r}"
