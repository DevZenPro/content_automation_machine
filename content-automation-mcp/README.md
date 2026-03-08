# Content Automation Machine -- MCP Server

An MCP server that automates video tweet creation by orchestrating Replicate (AI video generation) and Blotato (Twitter posting) APIs.

## Tools

| Tool | Description |
|------|-------------|
| `create_tweet` | Post a tweet via Blotato with optional media and threading |
| `create_video_tweet` | Generate a video from a prompt via Replicate, then post it as a tweet |

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

### Install

```bash
cd content-automation-mcp
uv sync --group dev
```

### Environment Variables

Create a `.env` file (or export directly):

```bash
REPLICATE_API_TOKEN=r8_...       # Required -- Replicate API token
BLOTATO_API_KEY=blot_...         # Required -- Blotato API key
BLOTATO_ACCOUNT_ID=acc_...       # Required -- Twitter account ID in Blotato
DRY_RUN=true                     # Optional -- skip API calls, log what would be sent
```

## Usage

### stdio transport (default)

```bash
uv run python -m content_automation.server
```

### Streamable HTTP transport

```bash
MCP_TRANSPORT=http MCP_HTTP_PORT=8000 uv run python -m content_automation.server
```

### Claude Desktop

Add to your Claude Desktop MCP config:

```json
{
  "mcpServers": {
    "content-automation": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/content-automation-mcp", "python", "-m", "content_automation.server"],
      "env": {
        "REPLICATE_API_TOKEN": "r8_...",
        "BLOTATO_API_KEY": "blot_...",
        "BLOTATO_ACCOUNT_ID": "acc_..."
      }
    }
  }
}
```

## Testing

```bash
uv run pytest                # run all tests
uv run pytest -v             # verbose output
uv run pytest --tb=short -q  # compact output
```

All tests run without API keys or network access:

- **Unit tests** mock service classes with `unittest.mock`
- **Integration tests** use FastMCP's in-process `Client` with `respx` HTTP mocking
- **Network isolation** -- a global `respx.mock` fixture blocks any unmocked HTTP request

## Project Structure

```
src/content_automation/
  server.py            # FastMCP server entry point
  config.py            # pydantic-settings configuration
  resilience.py        # Circuit breaker, rate limiter, cost budget
  tools/
    tweet.py           # create_tweet tool
    video_tweet.py     # create_video_tweet tool
  services/
    blotato.py         # Blotato API client (Twitter posting)
    replicate.py       # Replicate API client (video generation)
tests/
  conftest.py          # Shared fixtures, env setup, network isolation
  test_integration.py  # End-to-end tests via FastMCP Client + respx
  test_tools.py        # Tool-level tests with mocked services
  test_blotato_service.py
  test_replicate_service.py
  test_resilience.py
  test_config.py
  test_server.py
```
