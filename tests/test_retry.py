"""Tests for HTTP 429 retry logic in CloudflareCrawlClient."""
from unittest.mock import AsyncMock, patch

import pytest
from pytest_httpx import HTTPXMock

from mcp_cloudflare_crawl.cloudflare_client import CloudflareAPIError, CloudflareCrawlClient

ACCOUNT_ID = "test-account-id"
API_TOKEN = "test-api-token"
BASE_URL = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/browser-rendering/crawl"
JOB_ID = "c7f8s2d9-a8e7-4b6e-8e4d-3d4a1b2c3f4e"


@pytest.fixture()
def client() -> CloudflareCrawlClient:
    return CloudflareCrawlClient(api_token=API_TOKEN, account_id=ACCOUNT_ID)


class TestRetryOnPost:
    async def test_retries_on_429_and_succeeds(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            url=BASE_URL,
            status_code=429,
            json={"errors": [{"message": "Too Many Requests"}]},
        )
        httpx_mock.add_response(
            method="POST",
            url=BASE_URL,
            json={"success": True, "result": JOB_ID},
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.start_crawl(url="https://example.com/")

        assert result == JOB_ID

    async def test_retries_uses_exponential_backoff(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(method="POST", url=BASE_URL, status_code=429, json={})
        httpx_mock.add_response(method="POST", url=BASE_URL, status_code=429, json={})
        httpx_mock.add_response(
            method="POST", url=BASE_URL, json={"success": True, "result": JOB_ID}
        )

        sleep_calls: list[float] = []

        async def capture_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        with patch("asyncio.sleep", side_effect=capture_sleep):
            result = await client.start_crawl(url="https://example.com/")

        assert result == JOB_ID
        assert len(sleep_calls) == 2
        # Second delay should be greater than or equal to first (exponential)
        assert sleep_calls[1] >= sleep_calls[0]

    async def test_retries_respects_retry_after_header(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            url=BASE_URL,
            status_code=429,
            headers={"Retry-After": "3"},
            json={},
        )
        httpx_mock.add_response(
            method="POST",
            url=BASE_URL,
            json={"success": True, "result": JOB_ID},
        )

        sleep_calls: list[float] = []

        async def capture_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        with patch("asyncio.sleep", side_effect=capture_sleep):
            await client.start_crawl(url="https://example.com/")

        assert len(sleep_calls) == 1
        assert sleep_calls[0] == 3.0

    async def test_raises_after_max_retries_exhausted(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        # Default max_retries=3 means 1 initial + 3 retries = 4 total requests
        for _ in range(4):
            httpx_mock.add_response(
                method="POST",
                url=BASE_URL,
                status_code=429,
                json={"errors": [{"message": "Too Many Requests"}]},
            )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(CloudflareAPIError) as exc_info:
                await client.start_crawl(url="https://example.com/")

        assert exc_info.value.status_code == 429

    async def test_does_not_retry_on_non_429_errors(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            url=BASE_URL,
            status_code=400,
            json={"errors": [{"message": "Bad Request"}]},
        )

        sleep_mock = AsyncMock()
        with patch("asyncio.sleep", sleep_mock):
            with pytest.raises(CloudflareAPIError) as exc_info:
                await client.start_crawl(url="bad-url")

        assert exc_info.value.status_code == 400
        sleep_mock.assert_not_called()

    async def test_does_not_retry_on_401(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            url=BASE_URL,
            status_code=401,
            json={"errors": [{"message": "Unauthorized"}]},
        )

        sleep_mock = AsyncMock()
        with patch("asyncio.sleep", sleep_mock):
            with pytest.raises(CloudflareAPIError) as exc_info:
                await client.start_crawl(url="https://example.com/")

        assert exc_info.value.status_code == 401
        sleep_mock.assert_not_called()


class TestRetryOnGetAndDelete:
    async def test_retry_works_for_get_crawl_status(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/{JOB_ID}",
            status_code=429,
            json={},
        )
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
                    "browserSecondsUsed": 2.0,
                    "records": [],
                },
            },
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.get_crawl_status(job_id=JOB_ID)

        assert result["status"] == "completed"

    async def test_retry_works_for_cancel_crawl(
        self, client: CloudflareCrawlClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="DELETE",
            url=f"{BASE_URL}/{JOB_ID}",
            status_code=429,
            json={},
        )
        httpx_mock.add_response(
            method="DELETE",
            url=f"{BASE_URL}/{JOB_ID}",
            status_code=200,
            json={"success": True, "result": {}},
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.cancel_crawl(job_id=JOB_ID)

        assert result is True


class TestCustomRetryConfig:
    async def test_custom_max_retries(self, httpx_mock: HTTPXMock) -> None:
        custom_client = CloudflareCrawlClient(
            api_token=API_TOKEN, account_id=ACCOUNT_ID, max_retries=1
        )
        # 1 initial + 1 retry = 2 total requests, all 429 → should raise
        for _ in range(2):
            httpx_mock.add_response(method="POST", url=BASE_URL, status_code=429, json={})

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(CloudflareAPIError) as exc_info:
                await custom_client.start_crawl(url="https://example.com/")

        assert exc_info.value.status_code == 429

    async def test_custom_base_retry_delay(self, httpx_mock: HTTPXMock) -> None:
        custom_client = CloudflareCrawlClient(
            api_token=API_TOKEN, account_id=ACCOUNT_ID, base_retry_delay=5.0
        )
        httpx_mock.add_response(method="POST", url=BASE_URL, status_code=429, json={})
        httpx_mock.add_response(
            method="POST", url=BASE_URL, json={"success": True, "result": JOB_ID}
        )

        sleep_calls: list[float] = []

        async def capture_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        with patch("asyncio.sleep", side_effect=capture_sleep):
            await custom_client.start_crawl(url="https://example.com/")

        assert sleep_calls[0] == 5.0
