# mcp-cloudflare-crawl

An MCP server that exposes [Cloudflare's Browser Rendering Crawl API](https://developers.cloudflare.com/browser-rendering/rest-api/crawl-endpoint/) as tools for LLM clients.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- A Cloudflare account with Browser Rendering enabled
- A Cloudflare API token with **Browser Rendering - Edit** permission

## Setup

```bash
git clone https://github.com/yourname/mcp-cloudflare-crawl
cd mcp-cloudflare-crawl

cp .env.example .env
# Edit .env and fill in your credentials
```

`.env`:
```
CLOUDFLARE_API_TOKEN=your_api_token_here
CLOUDFLARE_ACCOUNT_ID=your_account_id_here
```

## Running

### stdio (default — for Claude Desktop and most MCP clients)

```bash
uv run mcp-cloudflare-crawl
```

### Streamable HTTP

```bash
uv run mcp-cloudflare-crawl --transport streamable-http
# Listens on http://127.0.0.1:8000/mcp by default

uv run mcp-cloudflare-crawl --transport streamable-http --host 0.0.0.0 --port 9000
```

## Claude Desktop Integration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "cloudflare-crawl": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/mcp-cloudflare-crawl",
        "mcp-cloudflare-crawl"
      ],
      "env": {
        "CLOUDFLARE_API_TOKEN": "your_api_token_here",
        "CLOUDFLARE_ACCOUNT_ID": "your_account_id_here"
      }
    }
  }
}
```

## Tools

### `crawl_start`

Submit a crawl job. Returns a `job_id` immediately — crawling happens asynchronously.

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | string | **Required.** Starting URL to crawl |
| `limit` | int | Max pages to crawl (default: 10, max: 100,000) |
| `depth` | int | Max link depth (default: 100,000) |
| `source` | string | URL discovery: `"all"`, `"sitemaps"`, or `"links"` |
| `formats` | list[string] | Output formats: `"html"`, `"markdown"`, `"json"` |
| `render` | bool | Execute JavaScript via headless browser (default: true) |
| `max_age` | int | Cache duration in seconds (default: 86400, max: 604800) |
| `modified_since` | int | Unix timestamp — only crawl pages modified since then |
| `crawl_purposes` | list[string] | Declare use: `"search"`, `"ai-input"`, `"ai-train"` |
| `include_patterns` | list[string] | URL patterns to include (`*` = no slash, `**` = any) |
| `exclude_patterns` | list[string] | URL patterns to exclude (higher priority than include) |
| `include_external_links` | bool | Follow links to external domains |
| `include_subdomains` | bool | Follow links to subdomains |

```json
{
  "url": "https://example.com/",
  "limit": 20,
  "formats": ["markdown"],
  "render": false
}
```

Response:
```json
{ "job_id": "c7f8s2d9-a8e7-4b6e-8e4d-3d4a1b2c3f4e" }
```

---

### `crawl_status`

Poll the status and results of a crawl job.

| Parameter | Type | Description |
|-----------|------|-------------|
| `job_id` | string | **Required.** Job ID from `crawl_start` |
| `cursor` | int | Pagination token for large result sets (>10 MB) |
| `limit` | int | Records per page |
| `status_filter` | string | Filter by record status: `queued`, `completed`, `disallowed`, `skipped`, `errored`, `cancelled` |

Response:
```json
{
  "id": "c7f8s2d9-...",
  "status": "completed",
  "total": 20,
  "finished": 20,
  "browser_seconds_used": 134.7,
  "cursor": null,
  "records": [
    {
      "url": "https://example.com/",
      "status": "completed",
      "markdown": "# Example Domain\n...",
      "metadata": { "status": 200, "title": "Example Domain", "url": "https://example.com/" }
    }
  ]
}
```

**Job statuses:** `running` · `completed` · `errored` · `cancelled_due_to_timeout` · `cancelled_due_to_limits` · `cancelled_by_user`

**Record statuses:** `queued` · `completed` · `errored` · `disallowed` · `skipped` · `cancelled`

---

### `crawl_cancel`

Cancel a running crawl job.

| Parameter | Type | Description |
|-----------|------|-------------|
| `job_id` | string | **Required.** Job ID from `crawl_start` |

---

### `crawl_and_wait`

Start a crawl and block until it completes, returning the final results. Combines `crawl_start` and `crawl_status` polling in one call.

Accepts all parameters from `crawl_start`, plus:

| Parameter | Type | Description |
|-----------|------|-------------|
| `poll_interval` | float | Seconds between status polls (default: 5.0) |
| `timeout` | float | Max seconds to wait (default: 300.0) |

Use this for small crawls (a few pages). For large crawls, use `crawl_start` + `crawl_status` separately to avoid timeouts.

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run tests with verbose output
uv run pytest -v
```

## Notes

- The Cloudflare Crawl API is **asynchronous** — `crawl_start` returns immediately, results are retrieved via `crawl_status`.
- The crawler respects `robots.txt` by default. Disallowed URLs appear with `"status": "disallowed"`.
- The `json` format uses Workers AI for structured extraction and incurs additional charges.
- Setting `render: false` skips the headless browser and fetches static HTML — faster and currently unbilled during beta.
- Results are retained for 14 days after a job completes. Maximum job runtime is 7 days.
- The crawler identifies itself as `CloudflareBrowserRenderingCrawler/1.0` and cannot bypass Cloudflare protection or CAPTCHAs.
