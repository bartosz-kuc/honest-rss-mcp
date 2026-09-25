"""rss-mcp — MCP server for RSS and Atom feeds.

Fetches, parses, and filters RSS 1.0/2.0 and Atom feeds using the standard
`feedparser` library. Works with any public feed URL. Nothing leaves your
machine except the HTTPS GET to the feed URL.

Tools: fetch_feed, search_entries, list_feed_metadata.

Author: Bartosz Kuć <firma@bartosza.pl>
Repo:   https://github.com/bartosz-kuc/honest-rss-mcp
License: MIT
"""

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any

import feedparser
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

USER_AGENT = "rss-mcp/1.0 (+https://github.com/bartosz-kuc/honest-rss-mcp)"
FETCH_TIMEOUT = 15  # seconds; socket timeout for connecting and for each read
MAX_URLS = 20  # cap for list_feed_metadata


class _TimeoutHandler(urllib.request.BaseHandler):
    """Sets a socket timeout on every request feedparser makes (feedparser 6 has no timeout option)."""

    def _set_timeout(self, req: urllib.request.Request) -> urllib.request.Request:
        req.timeout = FETCH_TIMEOUT
        return req

    http_request = https_request = ftp_request = _set_timeout


def _entry_to_dict(e: Any) -> dict:
    return {
        "title": getattr(e, "title", None),
        "link": getattr(e, "link", None),
        "published": getattr(e, "published", None) or getattr(e, "updated", None),
        "author": getattr(e, "author", None),
        "summary": getattr(e, "summary", None),
        "id": getattr(e, "id", None) or getattr(e, "link", None),
        "tags": [t.term for t in getattr(e, "tags", [])] if hasattr(e, "tags") else [],
    }


def _feed_info(f: feedparser.FeedParserDict, url: str, entry_count: int | None) -> dict:
    channel = f.feed
    info = {
        "url": url,
        "title": getattr(channel, "title", None),
        "subtitle": getattr(channel, "subtitle", None),
        "link": getattr(channel, "link", None),
        "language": getattr(channel, "language", None),
        "updated": getattr(channel, "updated", None),
        "generator": getattr(channel, "generator", None),
    }
    if entry_count is not None:
        info["total_entries"] = len(f.entries)
        info["returned"] = entry_count
    if f.bozo:
        info["parser_warning"] = str(f.bozo_exception)[:200] if f.bozo_exception else "feed is not fully well-formed"
    return info


def _parse(url: str) -> feedparser.FeedParserDict:
    timeout_msg = f"timed out after {FETCH_TIMEOUT}s fetching {url}"
    try:
        f = feedparser.parse(url, agent=USER_AGENT, handlers=[_TimeoutHandler()])
    except TimeoutError as exc:  # stalled while reading the response body
        raise TimeoutError(timeout_msg) from exc
    exc = f.get("bozo_exception")
    if isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, TimeoutError):
        # stalled while connecting or waiting for headers (feedparser reports URLError as bozo)
        raise TimeoutError(timeout_msg) from exc
    return f


server = Server("rss")


async def _list_tools() -> list[Tool]:
    return [
        Tool(
            name="fetch_feed",
            description=(
                "Fetch and parse an RSS or Atom feed. Returns feed metadata (title, subtitle, language) and the "
                "first `limit` entries in the order the feed lists them (title, link, published date, author, "
                "summary, tags). Entries are not re-sorted: most feeds list newest first, but that is not "
                "guaranteed. Use `limit` to cap how many entries you get back — feeds can be huge. Works with any "
                "publicly-accessible feed URL."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Feed URL (RSS 1.0, RSS 2.0, or Atom)"},
                    "limit": {"type": "integer", "default": 20, "description": "Maximum number of entries to return, taken from the start of the feed (default 20)"},
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="search_entries",
            description=(
                "Fetch a feed and return only entries whose title or summary contain a keyword (case-insensitive). "
                "Useful when you want the AI to check a feed for specific topics without wading through everything."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Feed URL"},
                    "query": {"type": "string", "description": "Keyword to match against title or summary (case-insensitive substring)"},
                    "limit": {"type": "integer", "default": 20, "description": "Maximum matches to return"},
                },
                "required": ["url", "query"],
            },
        ),
        Tool(
            name="list_feed_metadata",
            description=(
                f"Fetch metadata for one or more feeds (up to {MAX_URLS}) without returning their entries — title, "
                "subtitle, entry count, last update time. Useful for building a dashboard of feeds you follow."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": MAX_URLS,
                        "description": f"List of feed URLs (max {MAX_URLS})",
                    },
                },
                "required": ["urls"],
            },
        ),
    ]


async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "fetch_feed":
        url = arguments["url"]
        limit = int(arguments.get("limit", 20))
        f = _parse(url)
        entries = [_entry_to_dict(e) for e in f.entries[:limit]]
        result = {"feed": _feed_info(f, url, len(entries)), "entries": entries}
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    if name == "search_entries":
        url = arguments["url"]
        query = arguments["query"].lower().strip()
        if not query:
            raise ValueError("query must be non-empty")
        limit = int(arguments.get("limit", 20))
        f = _parse(url)
        matches: list[dict] = []
        for e in f.entries:
            title = (getattr(e, "title", "") or "").lower()
            summary = (getattr(e, "summary", "") or "").lower()
            if query in title or query in summary:
                matches.append(_entry_to_dict(e))
                if len(matches) >= limit:
                    break
        result = {"feed": _feed_info(f, url, len(matches)), "query": arguments["query"], "matches": matches}
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    if name == "list_feed_metadata":
        urls = arguments["urls"]
        if not isinstance(urls, list) or not urls:
            raise ValueError("urls must be a non-empty list")
        if len(urls) > MAX_URLS:
            raise ValueError(f"too many urls ({len(urls)}); list_feed_metadata accepts at most {MAX_URLS} per call")
        feeds = []
        for url in urls:
            try:
                f = _parse(url)
                info = _feed_info(f, url, None)
                info["total_entries"] = len(f.entries)
                feeds.append(info)
            except Exception as exc:  # noqa: BLE001
                feeds.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
        return [TextContent(type="text", text=json.dumps({"feeds": feeds}, ensure_ascii=False, indent=2))]

    raise ValueError(f"Unknown tool: {name}")


async def on_list_tools(ctx, params) -> ListToolsResult:
    return ListToolsResult(tools=await _list_tools())


async def on_call_tool(ctx, params) -> CallToolResult:
    return CallToolResult(content=await _call_tool(params.name, params.arguments or {}))


server.add_request_handler("tools/list", types.PaginatedRequestParams, on_list_tools)
server.add_request_handler("tools/call", types.CallToolRequestParams, on_call_tool)


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def sync_main():
    """Sync entry point for console script."""
    asyncio.run(main())


if __name__ == "__main__":
    sync_main()
