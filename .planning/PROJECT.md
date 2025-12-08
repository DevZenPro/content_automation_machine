# Content Automation Machine

## What This Is

A Python MCP server that serves as a generic content creation machine. It replaces the n8n video tweet pipeline with native MCP tools that OpenClaw (or any MCP-compatible agent) can call directly. Built with CrewAI + LangChain for workflow orchestration.

## Core Value

OpenClaw can generate and post video tweets (and plain tweets) without n8n middleware. The MCP server handles video generation, media upload, and social posting — all as simple tool calls.

## Active Requirements

### MCP Tool Interface
- Expose `create_video_tweet` tool — accepts tweet text, video prompt, and image (base64), returns posted tweet info
- Expose `create_tweet` tool — accepts tweet text, optional media URLs, posts directly
- Standard MCP server protocol (stdio or SSE transport)

### Video Tweet Pipeline (replaces n8n steps 4-6)
1. Receive image (base64) + video prompt from OpenClaw
2. Submit to Replicate WAN 2.2 I2V (image-to-video)
3. Poll Replicate until video is ready (initial 60s wait, then 30s polls)
4. Upload video to Blotato media endpoint
5. Post tweet with video via Blotato posts endpoint
6. Return success/failure + tweet details

### Plain Tweet Posting
- Direct tweet posting via Blotato API (no video generation)
- Support optional media URLs (pre-uploaded)

### Replicate Integration
- Model: `wan-video/wan-2.2-i2v-fast`
- API: `POST https://api.replicate.com/v1/models/wan-video/wan-2.2-i2v-fast/predictions`
- Auth: HTTP header (`Authorization: Bearer/Token`)
- Input params: prompt, image (data URI), resolution (720p), num_frames (81), fps (24), go_fast (true)
- Async polling: GET the prediction URL until status = "succeeded"
- Output: video URL in `output` field

### Blotato Integration
- Media upload: `POST https://backend.blotato.com/v2/media` with `url` body param
- Post creation: `POST https://backend.blotato.com/v2/posts` with post object
- Post structure: `{ post: { target: { targetType: "twitter" }, content: { text, platform: "twitter", mediaUrls: [url] }, accountId } }`
- Auth: HTTP header auth
- Account ID: configurable (currently "11500" for @clawquestsxyz)

## Out of Scope (handled elsewhere)

- **Token selection** — OpenClaw handles this
- **Image generation** — OpenClaw handles this (Gemini)
- **Tweet/prompt crafting** — OpenClaw handles this
- **Engagement tracking** — Deferred to v2 (Twitter likes/retweets feedback loop)
- **Content intelligence** — Deferred to v2

## Context

### Current n8n Workflow Being Replaced
The existing pipeline (`clawquests_video_twitter_pipeline.json`) runs as:
1. Webhook receives POST with `tweetText`, `videoPrompt`, `imageBase64`, `mimeType`
2. Creates Replicate prediction (WAN 2.2 I2V fast)
3. Waits 60s, then polls every 30s until succeeded
4. Uploads video URL to Blotato media endpoint
5. Creates tweet post via Blotato with media
6. Returns success response

### OpenClaw Integration
- OpenClaw runs locally, supports MCP servers via `openclaw.yaml`
- Currently triggers n8n webhook via `gn-video-trigger.sh` (base64 image POST)
- Plain tweets go directly via `blotato-tweet.sh` → Blotato API
- MCP server will be registered in `openclaw.yaml` as a tool provider

### Trigger Flow (after migration)
```
OpenClaw cron → selects token → generates image → crafts tweet + video prompt
  → calls MCP tool `create_video_tweet(tweet_text, video_prompt, image_base64, mime_type)`
  → MCP server: Replicate → poll → Blotato upload → Blotato post → return result
```

## Constraints

- **Language**: Python 3.11+
- **Orchestration**: CrewAI + LangChain
- **Protocol**: MCP (Model Context Protocol) — stdio and/or SSE transport
- **APIs**: Replicate (video gen), Blotato (social posting)
- **Deployment**: Must work both locally and deployed (cloud)
- **Config**: Environment variables for API keys and settings
- **Generic design**: Not ClawQuests-specific — reusable for any content automation

## Future (v2)

- Twitter engagement tracking (likes, retweets, replies)
- Content performance feedback loop → better content generation
- Multi-platform support (beyond Twitter)
- Analytics dashboard
