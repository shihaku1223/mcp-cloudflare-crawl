import pytest
import httpx
from pytest_httpx import HTTPXMock

from mcp_cloudflare_crawl.cloudflare_client import (
    CloudflareAPIError,
    CloudflareCrawlClient,
)

ACCOUNT_ID = "test-account-id"
API_TOKEN = "test-api-token"
BASE_URL = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/browser-rendering/crawl"
JOB_ID = "c7f8s2d9-a8e7-4b6e-8e4d-3d4a1b2c3f4e"


@pytest.fixture()
def client() -> CloudflareCrawlClient:
    return CloudflareCrawlClient(api_token=API_TOKEN, account_id=ACCOUNT_ID)


class TestStartCrawl:
    async def test_minimal_request_returns_job_id(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            url=BASE_URL,
            json={"success": True, "result": JOB_ID},
        )

        result = await client.start_crawl(url="https://example.com/")

        assert result == JOB_ID

    async def test_sends_bearer_token(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            url=BASE_URL,
            json={"success": True, "result": JOB_ID},
        )

        await client.start_crawl(url="https://example.com/")

        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers["Authorization"] == f"Bearer {API_TOKEN}"

    async def test_optional_params_included_in_body(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            url=BASE_URL,
            json={"success": True, "result": JOB_ID},
        )

        await client.start_crawl(
            url="https://example.com/",
            limit=50,
            formats=["markdown"],
            render=False,
            include_patterns=["https://example.com/**"],
            exclude_patterns=["https://example.com/private/**"],
        )

        import json
        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["limit"] == 50
        assert body["formats"] == ["markdown"]
        assert body["render"] is False
        assert body["options"]["includePatterns"] == ["https://example.com/**"]
        assert body["options"]["excludePatterns"] == ["https://example.com/private/**"]

    async def test_raises_on_api_error(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            url=BASE_URL,
            status_code=400,
            json={"success": False, "errors": [{"message": "Invalid URL"}]},
        )

        with pytest.raises(CloudflareAPIError) as exc_info:
            await client.start_crawl(url="not-a-url")

        assert "400" in str(exc_info.value)
        assert "Invalid URL" in str(exc_info.value)

    async def test_raises_on_auth_error(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            url=BASE_URL,
            status_code=401,
            json={"success": False, "errors": [{"message": "Unauthorized"}]},
        )

        with pytest.raises(CloudflareAPIError) as exc_info:
            await client.start_crawl(url="https://example.com/")

        assert exc_info.value.status_code == 401

    async def test_json_options_included_in_body(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST", url=BASE_URL, json={"success": True, "result": JOB_ID}
        )

        await client.start_crawl(
            url="https://example.com/",
            formats=["json"],
            json_options={"prompt": "Extract product prices", "response_format": {"type": "object"}},
        )

        import json
        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["jsonOptions"] == {
            "prompt": "Extract product prices",
            "response_format": {"type": "object"},
        }

    async def test_authenticate_included_in_body(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST", url=BASE_URL, json={"success": True, "result": JOB_ID}
        )

        await client.start_crawl(
            url="https://example.com/",
            authenticate={"username": "user", "password": "pass"},
        )

        import json
        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["authenticate"] == {"username": "user", "password": "pass"}

    async def test_extra_http_headers_included_in_body(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST", url=BASE_URL, json={"success": True, "result": JOB_ID}
        )

        await client.start_crawl(
            url="https://example.com/",
            extra_http_headers={"X-Custom-Token": "abc123"},
        )

        import json
        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        # Python param is extra_http_headers, wire field is setExtraHTTPHeaders
        assert body["setExtraHTTPHeaders"] == {"X-Custom-Token": "abc123"}

    async def test_cookies_included_in_body(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST", url=BASE_URL, json={"success": True, "result": JOB_ID}
        )
        cookies = [{"name": "session", "value": "abc123", "domain": "example.com"}]

        await client.start_crawl(url="https://example.com/", cookies=cookies)

        import json
        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["cookies"] == cookies

    async def test_goto_options_included_in_body(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST", url=BASE_URL, json={"success": True, "result": JOB_ID}
        )

        await client.start_crawl(
            url="https://example.com/",
            goto_options={"waitUntil": "networkidle2", "timeout": 30000},
        )

        import json
        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["gotoOptions"] == {"waitUntil": "networkidle2", "timeout": 30000}

    async def test_wait_for_selector_included_in_body(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST", url=BASE_URL, json={"success": True, "result": JOB_ID}
        )

        await client.start_crawl(
            url="https://example.com/",
            wait_for_selector={"selector": "#content", "timeout": 5000, "visible": True},
        )

        import json
        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["waitForSelector"] == {
            "selector": "#content",
            "timeout": 5000,
            "visible": True,
        }

    async def test_reject_resource_types_included_in_body(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST", url=BASE_URL, json={"success": True, "result": JOB_ID}
        )

        await client.start_crawl(
            url="https://example.com/",
            reject_resource_types=["image", "media", "font"],
        )

        import json
        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["rejectResourceTypes"] == ["image", "media", "font"]

    async def test_none_params_not_included_in_body(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        """Optional params set to None must not appear in the request body."""
        httpx_mock.add_response(
            method="POST", url=BASE_URL, json={"success": True, "result": JOB_ID}
        )

        await client.start_crawl(url="https://example.com/")

        import json
        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        for key in (
            "jsonOptions", "authenticate", "setExtraHTTPHeaders",
            "cookies", "gotoOptions", "waitForSelector", "rejectResourceTypes",
        ):
            assert key not in body


class TestGetCrawlStatus:
    async def test_returns_running_status(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/{JOB_ID}",
            json={
                "success": True,
                "result": {
                    "id": JOB_ID,
                    "status": "running",
                    "total": 10,
                    "finished": 3,
                    "browserSecondsUsed": 12.5,
                    "records": [],
                },
            },
        )

        result = await client.get_crawl_status(job_id=JOB_ID)

        assert result["status"] == "running"
        assert result["finished"] == 3
        assert result["total"] == 10

    async def test_returns_completed_status_with_records(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/{JOB_ID}",
            json={
                "success": True,
                "result": {
                    "id": JOB_ID,
                    "status": "completed",
                    "total": 1,
                    "finished": 1,
                    "browserSecondsUsed": 5.0,
                    "records": [
                        {
                            "url": "https://example.com/",
                            "status": "completed",
                            "markdown": "# Example",
                            "metadata": {"status": 200, "title": "Example"},
                        }
                    ],
                },
            },
        )

        result = await client.get_crawl_status(job_id=JOB_ID)

        assert result["status"] == "completed"
        assert len(result["records"]) == 1
        assert result["records"][0]["markdown"] == "# Example"

    async def test_passes_query_params(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/{JOB_ID}?cursor=10&limit=10&status=completed",
            json={
                "success": True,
                "result": {
                    "id": JOB_ID,
                    "status": "completed",
                    "total": 20,
                    "finished": 20,
                    "browserSecondsUsed": 10.0,
                    "records": [],
                },
            },
        )

        result = await client.get_crawl_status(
            job_id=JOB_ID, cursor=10, limit=10, status_filter="completed"
        )

        assert result["status"] == "completed"

    async def test_raises_on_not_found(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/{JOB_ID}",
            status_code=404,
            json={"success": False, "errors": [{"message": "Job not found"}]},
        )

        with pytest.raises(CloudflareAPIError) as exc_info:
            await client.get_crawl_status(job_id=JOB_ID)

        assert exc_info.value.status_code == 404


class TestCancelCrawl:
    async def test_cancel_returns_true(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="DELETE",
            url=f"{BASE_URL}/{JOB_ID}",
            status_code=200,
            json={"success": True, "result": {}},
        )

        result = await client.cancel_crawl(job_id=JOB_ID)

        assert result is True

    async def test_cancel_raises_on_error(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="DELETE",
            url=f"{BASE_URL}/{JOB_ID}",
            status_code=404,
            json={"success": False, "errors": [{"message": "Job not found"}]},
        )

        with pytest.raises(CloudflareAPIError):
            await client.cancel_crawl(job_id=JOB_ID)


class TestClientReuse:
    def test_http_client_stored_as_instance_attribute(self) -> None:
        """CloudflareCrawlClient must store AsyncClient as self._http."""
        c = CloudflareCrawlClient(api_token="tok", account_id="acc")
        assert hasattr(c, "_http")
        assert isinstance(c._http, httpx.AsyncClient)

    def test_same_http_instance_across_multiple_accesses(self) -> None:
        """self._http must return the same object on repeated access (not recreated)."""
        c = CloudflareCrawlClient(api_token="tok", account_id="acc")
        assert c._http is c._http
        first_id = id(c._http)
        _ = c._http  # access again
        assert id(c._http) == first_id
