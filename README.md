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

## Testing with curl

The server uses **SSE (Server-Sent Events)** format. Responses look like:

```
event: message
data: {"jsonrpc":"2.0","id":1,"result":{...}}
```

To parse with `jq`, extract the `data:` line first:

```bash
curl -s -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{...}' \
  | grep '^data:' | sed 's/^data: //' | jq .
```

### Step 1 — Initialize session and capture session ID

```bash
SESSION_ID=$(curl -s -D - -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "curl-test", "version": "1.0"}
    }
  }' | grep -i '^mcp-session-id:' | awk '{print $2}' | tr -d '\r')

echo "Session ID: $SESSION_ID"
```

### Step 2 — List available tools

```bash
curl -s -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  | grep '^data:' | sed 's/^data: //' | jq .
```

### Step 3 — Start a crawl (all optional parameters)

```bash
curl -s -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0", "id": 3, "method": "tools/call",
    "params": {
      "name": "crawl_start",
      "arguments": {
        "url": "https://www.exampledocs.com/docs/",
        "crawl_purposes": ["search"],
        "limit": 50,
        "depth": 2,
        "formats": ["markdown"],
        "render": false,
        "max_age": 7200,
        "modified_since": 1704067200,
        "source": "all",
        "include_external_links": true,
        "include_subdomains": true,
        "include_patterns": ["**/api/v1/*"],
        "exclude_patterns": ["*/learning-paths/*"],
        "reject_resource_types": ["image", "media", "font"],
        "goto_options": {"waitUntil": "networkidle2", "timeout": 30000},
        "wait_for_selector": {"selector": "#content", "timeout": 5000}
      }
    }
  }' | grep '^data:' | sed 's/^data: //' | jq .
```

### Step 4 — Poll status

```bash
curl -s -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0", "id": 4, "method": "tools/call",
    "params": {
      "name": "crawl_status",
      "arguments": {"job_id": "YOUR_JOB_ID"}
    }
  }' | grep '^data:' | sed 's/^data: //' | jq .
```

### Step 5 — Crawl with AI structured extraction

Requires `"json"` in `formats`. Uses Cloudflare Workers AI and incurs additional charges.

```bash
curl -s -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0", "id": 5, "method": "tools/call",
    "params": {
      "name": "crawl_and_wait",
      "arguments": {
        "url": "https://example.com/",
        "formats": ["json"],
        "limit": 5,
        "json_options": {
          "prompt": "Extract product names and prices",
          "response_format": {"type": "object"}
        },
        "timeout": 120.0
      }
    }
  }' | grep '^data:' | sed 's/^data: //' | jq .
```

### Step 6 — Crawl a password-protected site

```bash
curl -s -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0", "id": 6, "method": "tools/call",
    "params": {
      "name": "crawl_start",
      "arguments": {
        "url": "https://internal.example.com/docs/",
        "authenticate": {"username": "user", "password": "pass"},
        "extra_http_headers": {"X-API-Key": "abc123"},
        "cookies": [{"name": "session", "value": "xyz", "domain": "internal.example.com"}],
        "formats": ["markdown"]
      }
    }
  }' | grep '^data:' | sed 's/^data: //' | jq .
```

### Step 7 — List all stored jobs

```bash
curl -s -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0", "id": 7, "method": "tools/call",
    "params": {
      "name": "crawl_list",
      "arguments": {}
    }
  }' | grep '^data:' | sed 's/^data: //' | jq .
```

## Tools

### `crawl_start`

Submit a crawl job. Returns a `job_id` immediately — crawling happens asynchronously.
The job is automatically saved to the local SQLite database.

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
| `authenticate` | dict | HTTP auth credentials: `{"username": "...", "password": "..."}` |
| `extra_http_headers` | dict | Custom request headers: `{"X-API-Key": "..."}` |
| `json_options` | dict | AI extraction config (requires `"json"` in formats). Keys: `"prompt"`, `"response_format"`, `"custom_ai"` |
| `cookies` | list[dict] | Browser cookies: `[{"name": "...", "value": "...", "domain": "..."}]` |
| `goto_options` | dict | Navigation behaviour: `{"waitUntil": "networkidle2", "timeout": 30000}` |
| `wait_for_selector` | dict | Wait for DOM element: `{"selector": "#content", "timeout": 5000, "visible": true}` |
| `reject_resource_types` | list[string] | Block resource types: `"image"`, `"media"`, `"font"`, `"stylesheet"`, `"script"` |

Response:
```json
{ "job_id": "c7f8s2d9-a8e7-4b6e-8e4d-3d4a1b2c3f4e" }
```

---

### `crawl_status`

Poll the status and results of a crawl job. Also updates the job's status in the local database.

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

Start a crawl and block until it completes, returning the final results. Combines `crawl_start` and `crawl_status` polling in one call. The job is saved and status is updated in the local database throughout.

Accepts all parameters from `crawl_start`, plus:

| Parameter | Type | Description |
|-----------|------|-------------|
| `poll_interval` | float | Seconds between status polls (default: 5.0) |
| `timeout` | float | Max seconds to wait (default: 300.0) |

Use this for small crawls (a few pages). For large crawls, use `crawl_start` + `crawl_status` separately to avoid timeouts.

---

### `crawl_list`

List all crawl jobs stored in the local SQLite database. Jobs are recorded automatically on `crawl_start` and `crawl_and_wait`, and their status is updated on every `crawl_status` or `crawl_cancel` call.

| Parameter | Type | Description |
|-----------|------|-------------|
| `status_filter` | string | Filter by job status (see below) |
| `limit` | int | Max jobs to return (default: 50) |
| `offset` | int | Jobs to skip for pagination (default: 0) |

**Job statuses:** `submitted` · `running` · `completed` · `errored` · `cancelled_due_to_timeout` · `cancelled_due_to_limits` · `cancelled_by_user`

Response:
```json
{
  "jobs": [
    {
      "job_id": "c7f8s2d9-...",
      "url": "https://example.com/",
      "status": "completed",
      "created_at": "2026-03-25T00:00:00+00:00",
      "updated_at": "2026-03-25T00:01:00+00:00"
    }
  ],
  "count": 1
}
```

## Job Database

Jobs are persisted in a local SQLite database across server restarts.

**Default location:** `~/.local/share/mcp-cloudflare-crawl/jobs.db`

**Override with environment variable:**
```
MCP_DB_PATH=/path/to/custom/jobs.db
```

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
- HTTP 429 (rate limit) responses are automatically retried with exponential backoff (up to 3 retries: 1s → 2s → 4s). The `Retry-After` response header is respected when present.
