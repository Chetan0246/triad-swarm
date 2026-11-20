"""Tests for TinyFish Web Search and Fetch module with free service fallbacks."""

import pytest
import httpx
from triad.core.web import FreeWebEngine, SearchResult, TinyFishClient, WebFetchResponse, WebSearchResponse


def test_free_web_engine_html_stripping():
    html_sample = """
    <html>
        <head><title>FastAPI Quickstart</title></head>
        <body>
            <nav><a href="/home">Home</a></nav>
            <h1>FastAPI Framework</h1>
            <p>FastAPI is a modern, fast web framework for building APIs with Python.</p>
            <ul>
                <li>High performance</li>
                <li>Fast to code</li>
            </ul>
            <footer>Footer note</footer>
        </body>
    </html>
    """
    cleaned = FreeWebEngine._strip_html_to_markdown(html_sample)
    assert "FastAPI Framework" in cleaned
    assert "modern, fast web framework" in cleaned
    assert "High performance" in cleaned
    assert "<nav>" not in cleaned
    assert "<footer>" not in cleaned


@pytest.mark.asyncio
async def test_tinyfish_client_fallback_without_api_key(monkeypatch):
    monkeypatch.delenv("TINYFISH_API_KEY", raising=False)
    client = TinyFishClient()
    assert client.api_key is None

    # Free search fallback test
    resp = await client.search("python async queue", max_results=3)
    assert isinstance(resp, WebSearchResponse)
    assert resp.provider in ("free_duckduckgo_fallback", "tinyfish")
    assert resp.query == "python async queue"


@pytest.mark.asyncio
async def test_tinyfish_client_fetch_mock():
    client = TinyFishClient()
    # Test fetch with synthetic / error URL
    resp = await client.fetch("http://invalid.local.domain.test/404", max_chars=100)
    assert isinstance(resp, WebFetchResponse)
    assert resp.url == "http://invalid.local.domain.test/404"
    assert resp.provider == "free_httpx_scraper"


@pytest.mark.asyncio
async def test_tinyfish_with_mocked_api(monkeypatch):
    monkeypatch.setenv("TINYFISH_API_KEY", "test-key-12345")
    client = TinyFishClient()
    assert client.api_key == "test-key-12345"
