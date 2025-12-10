# Roadmap: Content Automation Machine

## Overview

This roadmap delivers a Python MCP server that replaces the existing n8n video tweet pipeline. The journey starts with a working MCP server skeleton (FastMCP + stdio), then builds the simpler Blotato tweet posting tool, followed by the complex Replicate video generation pipeline. Resilience features (circuit breakers, dry-run, budget tracking) layer on top of the working core, and a comprehensive test suite with full HTTP mocking validates everything end-to-end. CrewAI is explicitly excluded from core phases -- it can be added as a future enhancement.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation and Configuration** - FastMCP server skeleton with stdio transport, env config, structured logging, and tool stubs
- [ ] **Phase 2: Tweet Posting via Blotato** - Working `create_tweet` tool with Blotato API integration, retry logic, and error handling
- [ ] **Phase 3: Video Generation via Replicate** - Working `create_video_tweet` tool with full pipeline: Replicate generation, async polling, Blotato posting
- [ ] **Phase 4: Resilience and Production Hardening** - Circuit breakers, dry-run mode, cost budget counter, and rate limit awareness
- [ ] **Phase 5: Testing and Verification** - Unit tests, integration tests, and HTTP mocking with zero live API calls

## Phase Details

### Phase 1: Foundation and Configuration
**Goal**: A running MCP server that OpenClaw can connect to, with validated configuration and safe logging -- proving the transport layer works before any API integration
**Depends on**: Nothing (first phase)
**Requirements**: MCP-01, MCP-02, MCP-03, MCP-04, MCP-05, MCP-06, MCP-07
**Success Criteria** (what must be TRUE):
  1. MCP server starts via stdio transport and responds to tool discovery requests
  2. Configuration loads from environment variables with validation errors on missing required values
  3. All logging goes to stderr only -- zero bytes written to stdout outside MCP protocol
  4. Tool stubs for `create_tweet` and `create_video_tweet` are registered with typed Pydantic schemas and return placeholder responses
  5. Error responses use isError=True with actionable human-readable messages
**Plans**: TBD

Plans:
- [ ] 01-01: TBD
- [ ] 01-02: TBD

### Phase 2: Tweet Posting via Blotato
**Goal**: Users can post text tweets (with optional media) through the `create_tweet` MCP tool, with retry logic handling transient Blotato failures
**Depends on**: Phase 1
**Requirements**: POST-01, POST-02, POST-03, POST-04, POST-05, POST-07
**Success Criteria** (what must be TRUE):
  1. Calling `create_tweet` with text posts a tweet via Blotato API and returns the posted tweet details
  2. Calling `create_tweet` with text and media URLs attaches media to the posted tweet
  3. Transient Blotato API failures (5xx, timeouts) are retried with exponential backoff before surfacing an error
  4. Blotato auth uses the configured API key header and account ID from environment config
  5. Thread creation works via additionalPosts when multiple tweets are provided
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD

### Phase 3: Video Generation via Replicate
**Goal**: Users can generate a video from an image and post it as a tweet in a single `create_video_tweet` call, with progress updates and timeout protection
**Depends on**: Phase 2
**Requirements**: VIDEO-01, VIDEO-02, VIDEO-03, VIDEO-04, VIDEO-05, VIDEO-06, VIDEO-07, VIDEO-08
**Success Criteria** (what must be TRUE):
  1. Calling `create_video_tweet` with text, video prompt, and image (base64 or URL) creates a Replicate prediction, polls until completion, uploads video to Blotato, and posts the tweet
  2. Progress notifications are sent via MCP progressToken during video generation polling
  3. Video generation that exceeds 5 minutes is cancelled and returns an actionable timeout error
  4. Replicate video URL is uploaded to Blotato immediately after generation (before the 1-hour expiry)
  5. Video parameters (resolution, frames, fps) are configurable with sensible defaults (720p, 81 frames, 24fps)
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD

### Phase 4: Resilience and Production Hardening
**Goal**: The server gracefully handles API outages, prevents cost runaway, and supports safe testing via dry-run mode
**Depends on**: Phase 3
**Requirements**: RES-01, RES-02, RES-03, RES-04, POST-06
**Success Criteria** (what must be TRUE):
  1. Circuit breaker opens after repeated failures to an external service, returning fast errors instead of timing out
  2. Dry-run mode executes the full pipeline logic but skips actual API calls, logging what would have been sent
  3. Replicate cost budget counter tracks generation count and rejects requests when the configured limit is reached
  4. Rate limit awareness prevents exceeding Blotato's 30 req/min and Twitter's 100 posts/day limits
  5. Input validation catches malformed requests (missing text, invalid base64, bad URLs) with clear error messages before any API call
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD

### Phase 5: Testing and Verification
**Goal**: A comprehensive test suite validates all tools and services with zero live API calls, zero real tweets, and zero actual video generation
**Depends on**: Phase 4
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04
**Success Criteria** (what must be TRUE):
  1. Unit tests cover each service class (ReplicateService, BlotatoService) with mocked HTTP responses
  2. Integration tests exercise `create_tweet` and `create_video_tweet` tools end-to-end via FastMCP in-process client
  3. All HTTP calls are mocked via respx or pytest-httpx -- no network requests leave the test process
  4. Test suite passes in CI with no API keys, no network access, and no side effects
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation and Configuration | 0/2 | Not started | - |
| 2. Tweet Posting via Blotato | 0/2 | Not started | - |
| 3. Video Generation via Replicate | 0/2 | Not started | - |
| 4. Resilience and Production Hardening | 0/2 | Not started | - |
| 5. Testing and Verification | 0/2 | Not started | - |
