"""Tests for MCP tool functions via the Cloudflare client."""
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from mcp_cloudflare_crawl.cloudflare_client import CloudflareAPIError
from mcp_cloudflare_crawl.server import crawl_cancel, crawl_start, crawl_status, crawl_and_wait, crawl_list
from mcp_cloudflare_crawl.db import JobStore

JOB_ID = "c7f8s2d9-a8e7-4b6e-8e4d-3d4a1b2c3f4e"

COMPLETED_RESULT = {
    "id": JOB_ID,
    "status": "completed",
    "total": 1,
    "finished": 1,
    "browserSecondsUsed": 5.0,
    "cursor": None,
    "records": [
        {
            "url": "https://example.com/",
            "status": "completed",
            "markdown": "# Example",
            "metadata": {"status": 200, "title": "Example", "url": "https://example.com/"},
        }
    ],
}


def make_mock_client(
    start_return: str = JOB_ID,
    status_return: dict | None = None,
    cancel_return: bool = True,
) -> MagicMock:
    mock = MagicMock()
    mock.start_crawl = AsyncMock(return_value=start_return)
    mock.get_crawl_status = AsyncMock(return_value=status_return or COMPLETED_RESULT)
    mock.cancel_crawl = AsyncMock(return_value=cancel_return)
    return mock


def make_mock_store() -> MagicMock:
    mock = MagicMock()
    mock.init = AsyncMock()
    mock.save_job = AsyncMock()
    mock.update_status = AsyncMock()
    mock.list_jobs = AsyncMock(return_value=[])
    return mock


class TestCrawlStart:
    async def test_returns_job_id(self) -> None:
        mock_client = make_mock_client()
        mock_store = make_mock_store()
        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            result = await crawl_start(url="https://example.com/")

        assert result == {"job_id": JOB_ID}

    async def test_saves_job_to_store(self) -> None:
        mock_client = make_mock_client()
        mock_store = make_mock_store()
        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            await crawl_start(url="https://example.com/")

        mock_store.save_job.assert_called_once_with(job_id=JOB_ID, url="https://example.com/")

    async def test_passes_optional_params(self) -> None:
        mock_client = make_mock_client()
        mock_store = make_mock_store()
        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            await crawl_start(
                url="https://example.com/",
                limit=5,
                formats=["markdown"],
                render=False,
            )

        mock_client.start_crawl.assert_called_once_with(
            url="https://example.com/",
            limit=5,
            depth=None,
            source=None,
            formats=["markdown"],
            render=False,
            max_age=None,
            modified_since=None,
            crawl_purposes=None,
            include_patterns=None,
            exclude_patterns=None,
            include_external_links=None,
            include_subdomains=None,
            authenticate=None,
            extra_http_headers=None,
            json_options=None,
            cookies=None,
            goto_options=None,
            wait_for_selector=None,
            reject_resource_types=None,
        )

    async def test_passes_authenticate(self) -> None:
        mock_client = make_mock_client()
        mock_store = make_mock_store()
        auth = {"username": "user", "password": "pass"}
        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            await crawl_start(url="https://example.com/", authenticate=auth)

        call_kwargs = mock_client.start_crawl.call_args.kwargs
        assert call_kwargs["authenticate"] == auth

    async def test_passes_extra_http_headers(self) -> None:
        mock_client = make_mock_client()
        mock_store = make_mock_store()
        headers = {"X-Token": "abc123"}
        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            await crawl_start(url="https://example.com/", extra_http_headers=headers)

        call_kwargs = mock_client.start_crawl.call_args.kwargs
        assert call_kwargs["extra_http_headers"] == headers

    async def test_passes_json_options(self) -> None:
        mock_client = make_mock_client()
        mock_store = make_mock_store()
        json_opts = {"prompt": "Extract prices", "response_format": {"type": "object"}}
        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            await crawl_start(
                url="https://example.com/", formats=["json"], json_options=json_opts
            )

        call_kwargs = mock_client.start_crawl.call_args.kwargs
        assert call_kwargs["json_options"] == json_opts

    async def test_passes_cookies(self) -> None:
        mock_client = make_mock_client()
        mock_store = make_mock_store()
        cookies = [{"name": "session", "value": "abc", "domain": "example.com"}]
        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            await crawl_start(url="https://example.com/", cookies=cookies)

        call_kwargs = mock_client.start_crawl.call_args.kwargs
        assert call_kwargs["cookies"] == cookies

    async def test_passes_goto_options(self) -> None:
        mock_client = make_mock_client()
        mock_store = make_mock_store()
        goto = {"waitUntil": "networkidle2", "timeout": 30000}
        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            await crawl_start(url="https://example.com/", goto_options=goto)

        call_kwargs = mock_client.start_crawl.call_args.kwargs
        assert call_kwargs["goto_options"] == goto

    async def test_passes_wait_for_selector(self) -> None:
        mock_client = make_mock_client()
        mock_store = make_mock_store()
        wfs = {"selector": "#content", "timeout": 5000, "visible": True}
        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            await crawl_start(url="https://example.com/", wait_for_selector=wfs)

        call_kwargs = mock_client.start_crawl.call_args.kwargs
        assert call_kwargs["wait_for_selector"] == wfs

    async def test_passes_reject_resource_types(self) -> None:
        mock_client = make_mock_client()
        mock_store = make_mock_store()
        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            await crawl_start(
                url="https://example.com/", reject_resource_types=["image", "font"]
            )

        call_kwargs = mock_client.start_crawl.call_args.kwargs
        assert call_kwargs["reject_resource_types"] == ["image", "font"]

    async def test_wraps_api_error_as_runtime_error(self) -> None:
        mock_client = make_mock_client()
        mock_store = make_mock_store()
        mock_client.start_crawl = AsyncMock(
            side_effect=CloudflareAPIError(400, "Invalid URL")
        )
        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            with pytest.raises(RuntimeError, match="400"):
                await crawl_start(url="bad-url")


class TestCrawlStatus:
    async def test_returns_normalized_result(self) -> None:
        mock_client = make_mock_client()
        mock_store = make_mock_store()
        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            result = await crawl_status(job_id=JOB_ID)

        assert result["id"] == JOB_ID
        assert result["status"] == "completed"
        assert result["total"] == 1
        assert result["finished"] == 1
        assert len(result["records"]) == 1

    async def test_updates_store_status(self) -> None:
        mock_client = make_mock_client()
        mock_store = make_mock_store()
        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            await crawl_status(job_id=JOB_ID)

        mock_store.update_status.assert_called_once_with(job_id=JOB_ID, status="completed")

    async def test_running_status(self) -> None:
        running_result = {
            "id": JOB_ID,
            "status": "running",
            "total": 10,
            "finished": 3,
            "browserSecondsUsed": 12.5,
            "records": [],
        }
        mock_client = make_mock_client(status_return=running_result)
        mock_store = make_mock_store()
        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            result = await crawl_status(job_id=JOB_ID)

        assert result["status"] == "running"
        assert result["finished"] == 3

    async def test_errored_status(self) -> None:
        errored_result = {
            "id": JOB_ID,
            "status": "errored",
            "total": 1,
            "finished": 0,
            "browserSecondsUsed": 1.0,
            "records": [],
        }
        mock_client = make_mock_client(status_return=errored_result)
        mock_store = make_mock_store()
        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            result = await crawl_status(job_id=JOB_ID)

        assert result["status"] == "errored"

    async def test_wraps_api_error(self) -> None:
        mock_client = make_mock_client()
        mock_store = make_mock_store()
        mock_client.get_crawl_status = AsyncMock(
            side_effect=CloudflareAPIError(404, "Job not found")
        )
        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            with pytest.raises(RuntimeError, match="404"):
                await crawl_status(job_id="nonexistent-id")


class TestCrawlCancel:
    async def test_returns_success(self) -> None:
        mock_client = make_mock_client()
        mock_store = make_mock_store()
        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            result = await crawl_cancel(job_id=JOB_ID)

        assert result == {"success": True, "job_id": JOB_ID}

    async def test_updates_store_to_cancelled(self) -> None:
        mock_client = make_mock_client()
        mock_store = make_mock_store()
        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            await crawl_cancel(job_id=JOB_ID)

        mock_store.update_status.assert_called_once_with(job_id=JOB_ID, status="cancelled_by_user")

    async def test_wraps_api_error(self) -> None:
        mock_client = make_mock_client()
        mock_store = make_mock_store()
        mock_client.cancel_crawl = AsyncMock(
            side_effect=CloudflareAPIError(404, "Job not found")
        )
        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            with pytest.raises(RuntimeError, match="404"):
                await crawl_cancel(job_id="nonexistent-id")


class TestCrawlAndWait:
    async def test_completes_on_first_poll(self) -> None:
        mock_client = make_mock_client()
        mock_store = make_mock_store()
        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            result = await crawl_and_wait(
                url="https://example.com/",
                poll_interval=0.1,
                timeout=10.0,
            )

        assert result["status"] == "completed"
        assert result["id"] == JOB_ID
        assert len(result["records"]) == 1
        mock_store.save_job.assert_called_once_with(job_id=JOB_ID, url="https://example.com/")

    async def test_polls_until_complete(self) -> None:
        running = {
            "id": JOB_ID,
            "status": "running",
            "total": 5,
            "finished": 2,
            "browserSecondsUsed": 3.0,
            "records": [],
        }
        mock_client = make_mock_client()
        mock_store = make_mock_store()
        mock_client.get_crawl_status = AsyncMock(side_effect=[running, running, COMPLETED_RESULT])

        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            result = await crawl_and_wait(
                url="https://example.com/",
                poll_interval=0.1,
                timeout=60.0,
            )

        assert result["status"] == "completed"
        assert mock_client.get_crawl_status.call_count == 3

    async def test_raises_on_timeout(self) -> None:
        running = {
            "id": JOB_ID,
            "status": "running",
            "total": 100,
            "finished": 1,
            "browserSecondsUsed": 1.0,
            "records": [],
        }
        mock_client = make_mock_client(status_return=running)
        mock_store = make_mock_store()

        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="did not complete"):
                await crawl_and_wait(
                    url="https://example.com/",
                    poll_interval=6.0,
                    timeout=5.0,
                )

    async def test_returns_on_terminal_error_status(self) -> None:
        errored = {
            "id": JOB_ID,
            "status": "errored",
            "total": 1,
            "finished": 0,
            "browserSecondsUsed": 1.0,
            "records": [],
        }
        mock_client = make_mock_client(status_return=errored)
        mock_store = make_mock_store()

        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            result = await crawl_and_wait(
                url="https://example.com/",
                poll_interval=0.1,
                timeout=10.0,
            )

        assert result["status"] == "errored"

    async def test_returns_on_cancelled_status(self) -> None:
        cancelled = {
            "id": JOB_ID,
            "status": "cancelled_by_user",
            "total": 10,
            "finished": 3,
            "browserSecondsUsed": 8.0,
            "records": [],
        }
        mock_client = make_mock_client(status_return=cancelled)
        mock_store = make_mock_store()

        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            result = await crawl_and_wait(
                url="https://example.com/",
                poll_interval=0.1,
                timeout=10.0,
            )

        assert result["status"] == "cancelled_by_user"


class TestCrawlAndWaitNewParams:
    async def test_passes_all_new_params(self) -> None:
        mock_client = make_mock_client()
        mock_store = make_mock_store()
        auth = {"username": "user", "password": "pass"}
        headers = {"X-Token": "abc"}
        json_opts = {"prompt": "Extract data"}
        cookies = [{"name": "s", "value": "x"}]
        goto = {"waitUntil": "load"}
        wfs = {"selector": "#main"}
        rrt = ["image", "stylesheet"]

        with patch("mcp_cloudflare_crawl.server._get_client", return_value=mock_client), \
             patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            await crawl_and_wait(
                url="https://example.com/",
                authenticate=auth,
                extra_http_headers=headers,
                json_options=json_opts,
                cookies=cookies,
                goto_options=goto,
                wait_for_selector=wfs,
                reject_resource_types=rrt,
            )

        call_kwargs = mock_client.start_crawl.call_args.kwargs
        assert call_kwargs["authenticate"] == auth
        assert call_kwargs["extra_http_headers"] == headers
        assert call_kwargs["json_options"] == json_opts
        assert call_kwargs["cookies"] == cookies
        assert call_kwargs["goto_options"] == goto
        assert call_kwargs["wait_for_selector"] == wfs
        assert call_kwargs["reject_resource_types"] == rrt


class TestCrawlList:
    async def test_returns_empty_list(self) -> None:
        mock_store = make_mock_store()
        with patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            result = await crawl_list()

        assert result == {"jobs": [], "count": 0}

    async def test_returns_stored_jobs(self) -> None:
        mock_store = make_mock_store()
        mock_store.list_jobs = AsyncMock(return_value=[
            {"job_id": JOB_ID, "url": "https://example.com/", "status": "completed",
             "created_at": "2026-03-25T00:00:00+00:00", "updated_at": "2026-03-25T00:01:00+00:00"},
        ])
        with patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            result = await crawl_list()

        assert result["count"] == 1
        assert result["jobs"][0]["job_id"] == JOB_ID

    async def test_passes_status_filter(self) -> None:
        mock_store = make_mock_store()
        with patch("mcp_cloudflare_crawl.server._get_store", return_value=mock_store):
            await crawl_list(status_filter="completed", limit=10, offset=5)

        mock_store.list_jobs.assert_called_once_with(
            status_filter="completed", limit=10, offset=5
        )
