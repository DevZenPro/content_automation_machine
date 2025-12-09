# Requirements: Content Automation Machine

## MCP Server Foundation

| ID | Requirement | Priority | Phase |
|----|-------------|----------|-------|
| MCP-01 | FastMCP server with stdio transport | must | 1 |
| MCP-02 | Tool registration with typed schemas (Pydantic) | must | 1 |
| MCP-03 | Structured logging to stderr only (no stdout) | must | 1 |
| MCP-04 | Configuration via environment variables (pydantic-settings) | must | 1 |
| MCP-05 | Structured error responses with isError=True and actionable messages | must | 1 |
| MCP-06 | Progress notifications via MCP progressToken | must | 1 |
| MCP-07 | Streamable HTTP transport for remote deployment | should | 1 |

## Tweet Posting (Blotato)

| ID | Requirement | Priority | Phase |
|----|-------------|----------|-------|
| POST-01 | `create_tweet` tool — text-only tweet via Blotato API | must | 2 |
| POST-02 | `create_tweet` with optional media URLs | must | 2 |
| POST-03 | Blotato auth via API key header | must | 2 |
| POST-04 | Configurable account ID | must | 2 |
| POST-05 | Retry with exponential backoff on transient failures | must | 2 |
| POST-06 | Rate limit awareness (30 req/min Blotato, 100 posts/day Twitter) | should | 4 |
| POST-07 | Thread support via Blotato additionalPosts | should | 2 |

## Video Generation (Replicate)

| ID | Requirement | Priority | Phase |
|----|-------------|----------|-------|
| VIDEO-01 | `create_video_tweet` tool — full pipeline in one call | must | 3 |
| VIDEO-02 | Replicate WAN 2.2 I2V prediction creation | must | 3 |
| VIDEO-03 | Async polling with exponential backoff (2s base, 1.5x, 30s cap) | must | 3 |
| VIDEO-04 | 5-minute max timeout with deadline enforcement | must | 3 |
| VIDEO-05 | Progress notifications during video generation | must | 3 |
| VIDEO-06 | Immediate Blotato posting after gen (Replicate URLs expire in 1hr) | must | 3 |
| VIDEO-07 | Accept image as base64 data URI or public URL | must | 3 |
| VIDEO-08 | Configurable video params (resolution, frames, fps) | should | 3 |

## Resilience

| ID | Requirement | Priority | Phase |
|----|-------------|----------|-------|
| RES-01 | Circuit breaker per external service | should | 4 |
| RES-02 | Dry-run mode (test pipeline without posting) | should | 4 |
| RES-03 | Cost budget counter for Replicate generations | should | 4 |
| RES-04 | Input validation with clear error messages | must | 4 |

## Testing

| ID | Requirement | Priority | Phase |
|----|-------------|----------|-------|
| TEST-01 | Unit tests with mocked services | must | 5 |
| TEST-02 | Integration tests via FastMCP in-process client | must | 5 |
| TEST-03 | HTTP mocking (respx/pytest-httpx) — no live API calls | must | 5 |
| TEST-04 | No live tweets or video generation in tests | must | 5 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MCP-01 | Phase 1 | Pending |
| MCP-02 | Phase 1 | Pending |
| MCP-03 | Phase 1 | Pending |
| MCP-04 | Phase 1 | Pending |
| MCP-05 | Phase 1 | Pending |
| MCP-06 | Phase 1 | Pending |
| MCP-07 | Phase 1 | Pending |
| POST-01 | Phase 2 | Pending |
| POST-02 | Phase 2 | Pending |
| POST-03 | Phase 2 | Pending |
| POST-04 | Phase 2 | Pending |
| POST-05 | Phase 2 | Pending |
| POST-06 | Phase 4 | Pending |
| POST-07 | Phase 2 | Pending |
| VIDEO-01 | Phase 3 | Pending |
| VIDEO-02 | Phase 3 | Pending |
| VIDEO-03 | Phase 3 | Pending |
| VIDEO-04 | Phase 3 | Pending |
| VIDEO-05 | Phase 3 | Pending |
| VIDEO-06 | Phase 3 | Pending |
| VIDEO-07 | Phase 3 | Pending |
| VIDEO-08 | Phase 3 | Pending |
| RES-01 | Phase 4 | Pending |
| RES-02 | Phase 4 | Pending |
| RES-03 | Phase 4 | Pending |
| RES-04 | Phase 4 | Pending |
| TEST-01 | Phase 5 | Pending |
| TEST-02 | Phase 5 | Pending |
| TEST-03 | Phase 5 | Pending |
| TEST-04 | Phase 5 | Pending |

## Out of Scope (v2)

- Engagement tracking (likes, retweets, replies)
- Content performance feedback loop
- Multi-platform posting beyond Twitter
- Content scheduling (Blotato handles natively)
- Video editing/trimming
- `check_pipeline_status` tool
- `list_accounts` tool
- Webhook-based Replicate integration
- CrewAI content intelligence agents
