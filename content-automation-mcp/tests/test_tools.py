"""Tool-specific tests: stub responses, validation errors, progress notifications."""

# -- create_tweet tests -------------------------------------------------------


async def test_create_tweet_stub_returns_placeholder(mcp_client):
    """Calling create_tweet with valid text returns a STUB response."""
    result = await mcp_client.call_tool("create_tweet", {"text": "Hello world"})
    text = result.content[0].text
    assert "STUB" in text


async def test_create_tweet_empty_text_error(mcp_client):
    """Empty tweet text produces an error result mentioning 'cannot be empty'."""
    result = await mcp_client.call_tool(
        "create_tweet", {"text": ""}, raise_on_error=False
    )
    assert result.is_error is True
    assert "cannot be empty" in result.content[0].text.lower()


async def test_create_tweet_too_long_error(mcp_client):
    """Tweet text over 280 chars produces an error mentioning '280'."""
    long_text = "x" * 281
    result = await mcp_client.call_tool(
        "create_tweet", {"text": long_text}, raise_on_error=False
    )
    assert result.is_error is True
    assert "280" in result.content[0].text


async def test_create_tweet_with_media_urls(mcp_client):
    """create_tweet with media_urls returns a STUB (no error)."""
    result = await mcp_client.call_tool(
        "create_tweet",
        {"text": "Check this out", "media_urls": ["https://example.com/img.jpg"]},
    )
    assert "STUB" in result.content[0].text


async def test_create_tweet_with_thread_posts(mcp_client):
    """create_tweet with thread_posts returns a STUB (no error)."""
    result = await mcp_client.call_tool(
        "create_tweet",
        {"text": "Thread start", "thread_posts": ["Reply 1", "Reply 2"]},
    )
    assert "STUB" in result.content[0].text


# -- create_video_tweet tests -------------------------------------------------


async def test_create_video_tweet_stub(mcp_client):
    """Calling create_video_tweet with valid args returns a STUB response."""
    result = await mcp_client.call_tool(
        "create_video_tweet",
        {"prompt": "A sunset over the ocean", "tweet_text": "Beautiful sunset"},
    )
    text = result.content[0].text
    assert "STUB" in text


async def test_create_video_tweet_empty_prompt_error(mcp_client):
    """Empty video prompt produces an isError=True result."""
    result = await mcp_client.call_tool(
        "create_video_tweet",
        {"prompt": "", "tweet_text": "Some text"},
        raise_on_error=False,
    )
    assert result.is_error is True


async def test_create_video_tweet_empty_tweet_text_error(mcp_client):
    """Empty tweet_text in create_video_tweet produces an isError=True result."""
    result = await mcp_client.call_tool(
        "create_video_tweet",
        {"prompt": "A valid prompt", "tweet_text": ""},
        raise_on_error=False,
    )
    assert result.is_error is True
