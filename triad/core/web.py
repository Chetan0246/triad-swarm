"""Web integration module supporting TinyFish API and zero-cost free fallbacks.

Provides search and fetch capabilities for Triad Swarm agents, allowing workers
and architects to look up API docs, library references, and specs with bounded token usage.
"""

from __future__ import annotations

import html
import os
import re
import urllib.parse
from typing import List, Optional

import httpx
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Normalized search result item."""

    title: str
    url: str
    snippet: str
    source: str = "tinyfish"


class WebSearchResponse(BaseModel):
    """Normalized response for web search queries."""

    query: str
    results: List[SearchResult] = Field(default_factory=list)
    provider: str
    duration_seconds: float = 0.0


class WebFetchResponse(BaseModel):
    """Normalized response for web URL fetches."""

    url: str
    title: str = ""
    content: str
    content_type: str = "text/plain"
    provider: str
    truncated: bool = False
    duration_seconds: float = 0.0


class FreeWebEngine:
    """
    100% Free, zero-API-key fallback engine for search and web scraping.
    Ensures Triad Swarm operates at zero cost when third-party keys are absent.
    """

    @staticmethod
    def _strip_html_to_markdown(html_str: str) -> str:
        """Lightweight regex-based HTML cleaner producing clean text/markdown."""
        text = re.sub(r"<script[\s\S]*?</script>", "", html_str, flags=re.IGNORECASE)
        text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<nav[\s\S]*?</nav>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<footer[\s\S]*?</footer>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<!--[\s\S]*?-->", "", text)

        # Replace headings
        for i in range(1, 7):
            text = re.sub(rf"<h{i}[^>]*>([\s\S]*?)</h{i}>", rf"\n\n{'#' * i} \1\n", text, flags=re.IGNORECASE)

        # Replace links
        text = re.sub(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>', r"[\2](\1)", text, flags=re.IGNORECASE)
        # Replace paragraphs and breaks
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<li[^>]*>", "• ", text, flags=re.IGNORECASE)

        # Strip all remaining HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
        # Collapse excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @classmethod
    async def search(
        cls, query: str, max_results: int = 5, client: Optional[httpx.AsyncClient] = None
    ) -> List[SearchResult]:
        """Free web search fallback using DuckDuckGo Lite."""
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
        }
        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=15.0, follow_redirects=True)
            should_close = True

        results: List[SearchResult] = []
        try:
            # Query DuckDuckGo Lite endpoint (fast, zero challenge)
            resp = await client.post(
                "https://lite.duckduckgo.com/lite/",
                data={"q": query},
                headers=headers,
            )
            if resp.status_code == 200:
                # Attribute order is not guaranteed; locate rel/href independently
                # instead of relying on a single order-sensitive regex.
                links = []
                for anchor in re.finditer(r"<a\b([^>]*)>(.*?)</a>", resp.text, re.IGNORECASE | re.DOTALL):
                    attrs, title_html = anchor.groups()
                    if "nofollow" not in attrs.lower():
                        continue
                    href_match = re.search(r"href=[\"']([^\"']+)[\"']", attrs, re.IGNORECASE)
                    if href_match:
                        links.append((href_match.group(1), title_html))

                snippets = re.findall(
                    r"<td[^>]+class=[\"']result-snippet[\"'][^>]*>([\s\S]*?)</td>",
                    resp.text,
                )
                count = min(len(links), len(snippets), max_results)
                for i in range(count):
                    raw_url, raw_title = links[i]
                    actual_url = raw_url
                    if "uddg=" in raw_url:
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
                        if "uddg" in parsed:
                            actual_url = parsed["uddg"][0]
                    actual_url = urllib.parse.urljoin("https://duckduckgo.com", actual_url)
                    clean_title = html.unescape(re.sub(r"<[^>]+>", "", raw_title).strip())
                    clean_snippet = html.unescape(re.sub(r"<[^>]+>", "", snippets[i]).strip())
                    results.append(
                        SearchResult(
                            title=clean_title,
                            url=actual_url,
                            snippet=clean_snippet,
                            source="duckduckgo_lite_free",
                        )
                    )
        except Exception:
            pass
        finally:
            if should_close:
                await client.aclose()

        return results

    @classmethod
    async def fetch(
        cls, url: str, max_chars: int = 4000, client: Optional[httpx.AsyncClient] = None
    ) -> WebFetchResponse:
        """Free web scraper fallback with HTML cleaning and text extraction."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) TriadSwarm/0.3.0",
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9",
        }
        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=15.0, follow_redirects=True)
            should_close = True

        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code >= 400:
                return WebFetchResponse(
                    url=url,
                    title=f"HTTP {resp.status_code}",
                    content=f"Error fetching {url}: HTTP {resp.status_code} {resp.reason_phrase}",
                    provider="free_httpx_scraper",
                    truncated=False,
                )
            content_type = resp.headers.get("content-type", "")
            raw_text = resp.text

            title = ""
            title_match = re.search(r"<title[^>]*>([\s\S]*?)</title>", raw_text, re.IGNORECASE)
            if title_match:
                title = html.unescape(title_match.group(1).strip())

            if "html" in content_type:
                clean_text = cls._strip_html_to_markdown(raw_text)
            else:
                clean_text = raw_text

            truncated = len(clean_text) > max_chars
            final_content = clean_text[:max_chars]

            return WebFetchResponse(
                url=url,
                title=title,
                content=final_content,
                content_type=content_type,
                provider="free_httpx_scraper",
                truncated=truncated,
            )
        except Exception as e:
            return WebFetchResponse(
                url=url,
                title="",
                content=f"Error fetching {url}: {e}",
                provider="free_httpx_scraper",
                truncated=False,
            )
        finally:
            if should_close:
                await client.aclose()


class TinyFishClient:
    """
    Official TinyFish API client (`tinyfish.ai` / `agent.tinyfish.ai`).
    Leverages TinyFish for search and web scraping, with automatic zero-cost fallback.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("TINYFISH_API_KEY")
        self.base_url = (base_url or os.environ.get("TINYFISH_BASE_URL") or "https://agent.tinyfish.ai").rstrip("/")
        self.free_engine = FreeWebEngine()

    async def search(self, query: str, max_results: int = 5) -> WebSearchResponse:
        """Search the web via TinyFish API, falling back to free search when unauthenticated."""
        import time

        t0 = time.perf_counter()

        # If API key is provided, use TinyFish API
        if self.api_key:
            headers = {
                "X-API-Key": self.api_key,
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "query": query,
                "max_results": max_results,
            }
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.post(
                        f"{self.base_url}/v1/search",
                        json=payload,
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_items = data.get("results", data.get("data", []))
                        results = [
                            SearchResult(
                                title=item.get("title", "Result"),
                                url=item.get("url", ""),
                                snippet=item.get("snippet", item.get("description", "")),
                                source="tinyfish_api",
                            )
                            for item in raw_items[:max_results]
                        ]
                        return WebSearchResponse(
                            query=query,
                            results=results,
                            provider="tinyfish",
                            duration_seconds=time.perf_counter() - t0,
                        )
            except Exception:
                # Graceful fallback to free search
                pass

        # Free fallback execution
        results = await self.free_engine.search(query=query, max_results=max_results)
        return WebSearchResponse(
            query=query,
            results=results,
            provider="free_duckduckgo_fallback",
            duration_seconds=time.perf_counter() - t0,
        )

    async def fetch(self, url: str, max_chars: int = 4000) -> WebFetchResponse:
        """Fetch and extract web page content via TinyFish API or zero-cost scraper."""
        import time

        t0 = time.perf_counter()

        if self.api_key:
            headers = {
                "X-API-Key": self.api_key,
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            try:
                async with httpx.AsyncClient(timeout=25.0) as client:
                    resp = await client.post(
                        f"{self.base_url}/v1/fetch",
                        json={"url": url, "max_chars": max_chars},
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        content = data.get("content", data.get("text", ""))
                        return WebFetchResponse(
                            url=url,
                            title=data.get("title", ""),
                            content=content[:max_chars],
                            provider="tinyfish",
                            truncated=len(content) > max_chars,
                            duration_seconds=time.perf_counter() - t0,
                        )
            except Exception:
                pass

        # Free fallback scraper
        fallback_resp = await self.free_engine.fetch(url=url, max_chars=max_chars)
        fallback_resp.duration_seconds = time.perf_counter() - t0
        return fallback_resp
