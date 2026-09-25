# honest-rss-mcp

Local MCP server for RSS and Atom feeds. Universal, no cloud middle.

Part of the [honest-mcp family](https://github.com/bartosz-kuc?tab=repositories) of small, auditable, local-first MCP servers.

## Why

Every AI assistant should be able to read a feed. RSS is the last honest content protocol on the open web — no login, no algorithm, no tracker. This server hands feed data to your AI in the same shape as any other structured tool, so you can ask questions like "what did HN's frontpage look like this morning?" without scraping.

## Features

Three tools:

- `fetch_feed` — feed metadata + the first N entries in feed order (not re-sorted; most feeds list newest first, but that isn't guaranteed)
- `search_entries` — feed entries filtered by keyword in title/summary
- `list_feed_metadata` — quick dashboard view over up to 20 feeds at once (no full entry payload)

Handles RSS 1.0, RSS 2.0, and Atom — whatever `feedparser` handles. Network fetches use a 15-second socket timeout (for connecting and for each read), so a feed server that stops responding returns an error instead of hanging the tool.

## Requirements

- Python 3.10+

## Setup

```bash
git clone https://github.com/bartosz-kuc/honest-rss-mcp.git
cd honest-rss-mcp
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

On Windows use `python` instead of `python3`, and `venv\Scripts\pip` / `venv\Scripts\python` instead of the `venv/bin/...` paths shown here and in the configs below.

Register with Claude Code:

```bash
claude mcp add rss /absolute/path/to/venv/bin/python /absolute/path/to/server.py
```

Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rss": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["/absolute/path/to/server.py"]
    }
  }
}
```

## Example usage

> "What's on Hacker News right now?"

`fetch_feed(url="https://news.ycombinator.com/rss", limit=10)`

> "Anything about MCP in the Anthropic blog feed?"

`search_entries(url="https://www.anthropic.com/rss.xml", query="MCP")`

> "Give me a summary line for each of these five feeds."

`list_feed_metadata(urls=["...", "...", ...])`

## Data flow

```
Your AI client
     ↕  MCP stdio
This server (Python, on your machine)
     ↕  HTTPS
Feed URL
```

Nothing else. No aggregator server, no analytics.

## Author

**Bartosz Kuć** — Warsaw-based developer, JDG owner running [skanfirmy.pl](https://skanfirmy.pl).

- GitHub: https://github.com/bartosz-kuc

- Email: firma@bartosza.pl

## Consulting

Available for consulting on Polish tax and business integrations (KSeF, GUS/NFZ/GIOŚ APIs, mBank data), MCP server design, and AI-assisted tooling for JDGs and small teams. See **[skanfirmy.pl/uslugi](https://skanfirmy.pl/uslugi)** for productized packages (audit 3k PLN, setup 8-15k PLN, retainer 2-4k PLN/mo), or reach out via email.

## License

MIT — see [LICENSE](LICENSE).

## Related

- Part of the honest-mcp family — see the [family index](https://github.com/bartosz-kuc?tab=repositories).
