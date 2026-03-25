import asyncio
from typing import Any

import httpx

BASE_URL = "https://api.cloudflare.com/client/v4/accounts/{account_id}/browser-rendering/crawl"


class CloudflareAPIError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"Cloudflare API error {status_code}: {message}")


class CloudflareCrawlClient:
    def __init__(
        self,
        api_token: str,
        account_id: str,
        max_retries: int = 3,
        base_retry_delay: float = 1.0,
    ) -> None:
        self._account_id = account_id
        self._base_url = BASE_URL.format(account_id=account_id)
        self._headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        self._max_retries = max_retries
        self._base_retry_delay = base_retry_delay

    def _raise_for_error(self, response: httpx.Response) -> None:
        if not response.is_success:
            try:
                body = response.json()
                errors = body.get("errors", [])
                message = errors[0].get("message", response.text) if errors else response.text
            except Exception:
                message = response.text
            raise CloudflareAPIError(response.status_code, message)

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Execute an HTTP request, retrying automatically on 429 rate-limit responses.

        Respects the Retry-After response header when present; otherwise uses
        exponential backoff starting at base_retry_delay seconds.
        """
        async with httpx.AsyncClient() as http:
            response = await http.request(method, url, headers=self._headers, **kwargs)
            for attempt in range(self._max_retries):
                if response.status_code != 429:
                    return response
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after is not None else self._base_retry_delay * (2 ** attempt)
                except ValueError:
                    delay = self._base_retry_delay * (2 ** attempt)
                await asyncio.sleep(delay)
                response = await http.request(method, url, headers=self._headers, **kwargs)
        return response

    async def start_crawl(
        self,
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
    ) -> str:
        body: dict[str, Any] = {"url": url}

        if limit is not None:
            body["limit"] = limit
        if depth is not None:
            body["depth"] = depth
        if source is not None:
            body["source"] = source
        if formats is not None:
            body["formats"] = formats
        if render is not None:
            body["render"] = render
        if max_age is not None:
            body["maxAge"] = max_age
        if modified_since is not None:
            body["modifiedSince"] = modified_since
        if crawl_purposes is not None:
            body["crawlPurposes"] = crawl_purposes
        if authenticate is not None:
            body["authenticate"] = authenticate
        if extra_http_headers is not None:
            body["setExtraHTTPHeaders"] = extra_http_headers
        if json_options is not None:
            body["jsonOptions"] = json_options
        if cookies is not None:
            body["cookies"] = cookies
        if goto_options is not None:
            body["gotoOptions"] = goto_options
        if wait_for_selector is not None:
            body["waitForSelector"] = wait_for_selector
        if reject_resource_types is not None:
            body["rejectResourceTypes"] = reject_resource_types

        options: dict[str, Any] = {}
        if include_external_links is not None:
            options["includeExternalLinks"] = include_external_links
        if include_subdomains is not None:
            options["includeSubdomains"] = include_subdomains
        if include_patterns is not None:
            options["includePatterns"] = include_patterns
        if exclude_patterns is not None:
            options["excludePatterns"] = exclude_patterns
        if options:
            body["options"] = options

        response = await self._request("POST", self._base_url, json=body)
        self._raise_for_error(response)
        return response.json()["result"]

    async def get_crawl_status(
        self,
        job_id: str,
        cursor: int | None = None,
        limit: int | None = None,
        status_filter: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if cursor is not None:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = limit
        if status_filter is not None:
            params["status"] = status_filter

        response = await self._request(
            "GET", f"{self._base_url}/{job_id}", params=params
        )
        self._raise_for_error(response)
        return response.json()["result"]

    async def cancel_crawl(self, job_id: str) -> bool:
        response = await self._request("DELETE", f"{self._base_url}/{job_id}")
        self._raise_for_error(response)
        return True
