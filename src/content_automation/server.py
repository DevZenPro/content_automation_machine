"""FastMCP server for content automation.

Supports stdio (default) and streamable HTTP transports.

Launch methods:
  stdio:  uv run python -m content_automation.server
  http:   MCP_TRANSPORT=http MCP_HTTP_PORT=8000 uv run python -m content_automation.server
  cli:    fastmcp run content_automation.server:mcp --transport http --port 8000
"""

import logging
import sys

# Force all logging to stderr before any other imports
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    stream=sys.stderr,
    force=True,
)

import structlog  # noqa: E402

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
)

from fastmcp import FastMCP  # noqa: E402

from content_automation.config import get_settings  # noqa: E402

# Validate config at startup -- crash early on missing env vars
settings = get_settings()

mcp = FastMCP("Content Automation Machine")

# Register tools via side-effect imports (must come after mcp creation)
import content_automation.tools.tweet  # noqa: E402, F401
import content_automation.tools.video_tweet  # noqa: E402, F401

if __name__ == "__main__":
    if settings.mcp_transport == "http":
        mcp.run(transport="streamable-http", port=settings.mcp_http_port)
    else:
        mcp.run()
