import asyncio
from typing import Any

from mcp.server.fastmcp import FastMCP

from .cloudflare_client import CloudflareAPIError, CloudflareCrawlClient
from .config import get_account_id, get_api_token, get_db_path
from .db import JobStore

mcp = FastMCP("mcp-cloudflare-crawl")


def _get_client() -> CloudflareCrawlClient:
    return CloudflareCrawlClient(
        api_token=get_api_token(),
        account_id=get_account_id(),
    )


def _get_store() -> JobStore:
    return JobStore(get_db_path())


@mcp.tool()
async def crawl_start(
    url: str,
    limit: int | None = None,
    depth: int | None = None,
    source: str | None = None,
    formats: list[str] | None = None,
    render: bool | None = None,
    max_age: int | None = None,
    modified_since: int | None = None,
    crawl_purposes: list[str] | None = None,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    include_external_links: bool | None = None,
    include_subdomains: bool | None = None,
    authenticate: dict[str, str] | None = None,
    extra_http_headers: dict[str, str] | None = None,
    json_options: dict[str, Any] | None = None,
    cookies: list[dict[str, Any]] | None = None,
    goto_options: dict[str, Any] | None = None,
    wait_for_selector: dict[str, Any] | None = None,
    reject_resource_types: list[str] | None = None,
) -> dict[str, Any]:
    """Start an asynchronous crawl job using Cloudflare's Browser Rendering Crawl API.

    Submits a crawl job and returns a job_id immediately. Use crawl_status to poll
    for results, or use crawl_and_wait to block until completion.

    Args:
        url: The starting URL to crawl (required).
        limit: Maximum number of pages to crawl (default: 10, max: 100000).
        depth: Maximum link depth to follow (default: 100000).
        source: URL discovery source — "all", "sitemaps", or "links" (default: "all").
        formats: Output formats — any of ["html", "markdown", "json"] (default: ["html"]).
                 Note: "json" uses Workers AI and incurs additional charges.
        render: Whether to execute JavaScript via headless browser (default: true).
                Set false for faster, unbilled static HTML fetching.
        max_age: Cache duration in seconds (default: 86400, max: 604800).
        modified_since: Unix timestamp — only crawl pages modified since this time.
        crawl_purposes: Declare content use — any of ["search", "ai-input", "ai-train"].
        include_patterns: URL patterns to include (* = any chars except /, ** = any chars).
        exclude_patterns: URL patterns to exclude (takes priority over include_patterns).
        include_external_links: Whether to follow links to external domains.
        include_subdomains: Whether to follow links to subdomains.
        authenticate: HTTP authentication credentials for protected sites.
                      Example: {"username": "user", "password": "pass"}.
        extra_http_headers: Custom HTTP headers to send with each crawl request.
                            Example: {"X-API-Key": "abc123"}.
        json_options: AI-based structured data extraction config (requires "json" in formats).
                      Keys: "prompt" (str) — extraction instruction,
                      "response_format" (dict) — JSON schema for output,
                      "custom_ai" (dict) — custom AI model config.
        cookies: Browser cookies to set during the crawl.
                 Example: [{"name": "session", "value": "abc", "domain": "example.com"}].
        goto_options: Page navigation behaviour.
                      Keys: "waitUntil" (str) — e.g. "networkidle2", "load", "domcontentloaded";
                      "timeout" (int) — navigation timeout in milliseconds.
        wait_for_selector: Wait for a DOM element before scraping each page.
                           Keys: "selector" (str), "timeout" (int, ms), "visible" (bool).
        reject_resource_types: Resource types to block to speed up crawls and reduce cost.
                                Values: "image", "media", "font", "stylesheet", "script", etc.

    Returns:
        {"job_id": "<uuid>"} — use this ID with crawl_status or crawl_cancel.
    """
    try:
        client = _get_client()
        job_id = await client.start_crawl(
            url=url,
            limit=limit,
            depth=depth,
            source=source,
            formats=formats,
            render=render,
            max_age=max_age,
            modified_since=modified_since,
            crawl_purposes=crawl_purposes,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            include_external_links=include_external_links,
            include_subdomains=include_subdomains,
            authenticate=authenticate,
            extra_http_headers=extra_http_headers,
            json_options=json_options,
            cookies=cookies,
            goto_options=goto_options,
            wait_for_selector=wait_for_selector,
            reject_resource_types=reject_resource_types,
        )
        store = _get_store()
        await store.init()
        await store.save_job(job_id=job_id, url=url)
        return {"job_id": job_id}
    except CloudflareAPIError as e:
        raise RuntimeError(str(e)) from e


@mcp.tool()
async def crawl_status(
    job_id: str,
    cursor: int | None = None,
    limit: int | None = None,
    status_filter: str | None = None,
) -> dict[str, Any]:
    """Check the status and retrieve results of a crawl job.

    For large result sets (>10 MB), the response includes a "cursor" value.
    Pass it back in the next call to paginate through results.

    Args:
        job_id: The crawl job ID returned by crawl_start.
        cursor: Pagination token from a previous response (for large result sets).
        limit: Number of records to return per page.
        status_filter: Filter records by status — one of:
                       "queued", "completed", "disallowed", "skipped",
                       "errored", "cancelled".

    Returns:
        {
            "id": "<job_id>",
            "status": "running|completed|errored|cancelled_due_to_timeout|cancelled_due_to_limits|cancelled_by_user",
            "total": <int>,
            "finished": <int>,
            "browser_seconds_used": <float>,
            "cursor": <int|null>,
            "records": [
                {
                    "url": "...",
                    "status": "completed|errored|queued|disallowed|skipped|cancelled",
                    "html": "...",       # if html format requested
                    "markdown": "...",   # if markdown format requested
                    "metadata": {"status": 200, "title": "...", "url": "..."}
                },
                ...
            ]
        }
    """
    try:
        client = _get_client()
        result = await client.get_crawl_status(
            job_id=job_id,
            cursor=cursor,
            limit=limit,
            status_filter=status_filter,
        )
        job_status = result.get("status")
        if job_status:
            store = _get_store()
            await store.init()
            await store.update_status(job_id=job_id, status=job_status)
        return {
            "id": result.get("id"),
            "status": job_status,
            "total": result.get("total"),
            "finished": result.get("finished"),
            "browser_seconds_used": result.get("browserSecondsUsed"),
            "cursor": result.get("cursor"),
            "records": result.get("records", []),
        }
    except CloudflareAPIError as e:
        raise RuntimeError(str(e)) from e


@mcp.tool()
async def crawl_cancel(job_id: str) -> dict[str, Any]:
    """Cancel a running crawl job.

    Args:
        job_id: The crawl job ID returned by crawl_start.

    Returns:
        {"success": true, "job_id": "<job_id>"}
    """
    try:
        client = _get_client()
        await client.cancel_crawl(job_id=job_id)
        store = _get_store()
        await store.init()
        await store.update_status(job_id=job_id, status="cancelled_by_user")
        return {"success": True, "job_id": job_id}
    except CloudflareAPIError as e:
        raise RuntimeError(str(e)) from e


@mcp.tool()
async def crawl_and_wait(
    url: str,
    limit: int | None = None,
    depth: int | None = None,
    source: str | None = None,
    formats: list[str] | None = None,
    render: bool | None = None,
    max_age: int | None = None,
    modified_since: int | None = None,
    crawl_purposes: list[str] | None = None,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    include_external_links: bool | None = None,
    include_subdomains: bool | None = None,
    authenticate: dict[str, str] | None = None,
    extra_http_headers: dict[str, str] | None = None,
    json_options: dict[str, Any] | None = None,
    cookies: list[dict[str, Any]] | None = None,
    goto_options: dict[str, Any] | None = None,
    wait_for_selector: dict[str, Any] | None = None,
    reject_resource_types: list[str] | None = None,
    poll_interval: float = 5.0,
    timeout: float = 300.0,
) -> dict[str, Any]:
    """Start a crawl and wait for it to complete, returning the final results.

    This is a convenience tool that combines crawl_start and crawl_status polling.
    Suitable for small crawls (few pages). For large crawls, use crawl_start and
    crawl_status separately to avoid timeout issues.

    Args:
        url: The starting URL to crawl (required).
        limit: Maximum pages to crawl (default: 10, max: 100000).
        depth: Maximum link depth (default: 100000).
        source: URL discovery source — "all", "sitemaps", or "links" (default: "all").
        formats: Output formats — any of ["html", "markdown", "json"] (default: ["html"]).
                 Note: "json" uses Workers AI and incurs additional charges.
        render: Whether to execute JavaScript via headless browser (default: true).
        max_age: Cache duration in seconds (default: 86400, max: 604800).
        modified_since: Unix timestamp — only crawl pages modified since this time.
        crawl_purposes: Declare content use — any of ["search", "ai-input", "ai-train"].
        include_patterns: URL patterns to include (* = any chars except /, ** = any chars).
        exclude_patterns: URL patterns to exclude (takes priority over include_patterns).
        include_external_links: Whether to follow links to external domains.
        include_subdomains: Whether to follow links to subdomains.
        authenticate: HTTP authentication credentials for protected sites.
                      Example: {"username": "user", "password": "pass"}.
        extra_http_headers: Custom HTTP headers to send with each crawl request.
                            Example: {"X-API-Key": "abc123"}.
        json_options: AI-based structured data extraction config (requires "json" in formats).
                      Keys: "prompt" (str) — extraction instruction,
                      "response_format" (dict) — JSON schema for output,
                      "custom_ai" (dict) — custom AI model config.
        cookies: Browser cookies to set during the crawl.
                 Example: [{"name": "session", "value": "abc", "domain": "example.com"}].
        goto_options: Page navigation behaviour.
                      Keys: "waitUntil" (str) — e.g. "networkidle2", "load", "domcontentloaded";
                      "timeout" (int) — navigation timeout in milliseconds.
        wait_for_selector: Wait for a DOM element before scraping each page.
                           Keys: "selector" (str), "timeout" (int, ms), "visible" (bool).
        reject_resource_types: Resource types to block to speed up crawls and reduce cost.
                                Values: "image", "media", "font", "stylesheet", "script", etc.
        poll_interval: Seconds between status polls (default: 5.0).
        timeout: Maximum seconds to wait for completion (default: 300.0).

    Returns:
        Final crawl result (same shape as crawl_status) once the job completes,
        or raises RuntimeError if the timeout is exceeded.
    """
    terminal_statuses = {
        "completed",
        "errored",
        "cancelled_due_to_timeout",
        "cancelled_due_to_limits",
        "cancelled_by_user",
    }

    try:
        client = _get_client()
        store = _get_store()
        await store.init()

        job_id = await client.start_crawl(
            url=url,
            limit=limit,
            depth=depth,
            source=source,
            formats=formats,
            render=render,
            max_age=max_age,
            modified_since=modified_since,
            crawl_purposes=crawl_purposes,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            include_external_links=include_external_links,
            include_subdomains=include_subdomains,
            authenticate=authenticate,
            extra_http_headers=extra_http_headers,
            json_options=json_options,
            cookies=cookies,
            goto_options=goto_options,
            wait_for_selector=wait_for_selector,
            reject_resource_types=reject_resource_types,
        )
        await store.save_job(job_id=job_id, url=url)

        elapsed = 0.0
        while elapsed < timeout:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            result = await client.get_crawl_status(job_id=job_id)
            status = result.get("status")

            if status:
                await store.update_status(job_id=job_id, status=status)

            if status in terminal_statuses:
                return {
                    "id": result.get("id"),
                    "status": status,
                    "total": result.get("total"),
                    "finished": result.get("finished"),
                    "browser_seconds_used": result.get("browserSecondsUsed"),
                    "cursor": result.get("cursor"),
                    "records": result.get("records", []),
                }

        raise RuntimeError(
            f"Crawl job {job_id} did not complete within {timeout}s. "
            f"Use crawl_status to continue polling."
        )

    except CloudflareAPIError as e:
        raise RuntimeError(str(e)) from e


@mcp.tool()
async def crawl_list(
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List all crawl jobs stored in the local database.

    Jobs are recorded automatically when crawl_start or crawl_and_wait is called.
    Status is updated whenever crawl_status is polled.

    Args:
        status_filter: Filter by job status — one of:
                       "submitted", "running", "completed", "errored",
                       "cancelled_due_to_timeout", "cancelled_due_to_limits",
                       "cancelled_by_user".
        limit: Maximum number of jobs to return (default: 50).
        offset: Number of jobs to skip for pagination (default: 0).

    Returns:
        {
            "jobs": [
                {
                    "job_id": "...",
                    "url": "https://...",
                    "status": "completed",
                    "created_at": "2026-03-25T00:00:00+00:00",
                    "updated_at": "2026-03-25T00:01:00+00:00"
                },
                ...
            ],
            "count": <int>
        }
    """
    store = _get_store()
    await store.init()
    jobs = await store.list_jobs(
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )
    return {"jobs": jobs, "count": len(jobs)}
