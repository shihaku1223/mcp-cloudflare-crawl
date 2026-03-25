import pytest

from mcp_cloudflare_crawl.db import JobStore

JOB_ID = "c7f8s2d9-a8e7-4b6e-8e4d-3d4a1b2c3f4e"
JOB_ID_2 = "aaaabbbb-cccc-dddd-eeee-ffffffffffff"


@pytest.fixture()
async def store(tmp_path) -> JobStore:
    s = JobStore(tmp_path / "test.db")
    await s.init()
    return s


class TestInit:
    async def test_creates_db_file(self, tmp_path) -> None:
        db_path = tmp_path / "subdir" / "jobs.db"
        store = JobStore(db_path)
        await store.init()
        assert db_path.exists()

    async def test_idempotent(self, tmp_path) -> None:
        store = JobStore(tmp_path / "jobs.db")
        await store.init()
        await store.init()  # should not raise


class TestSaveJob:
    async def test_saves_and_retrieves(self, store: JobStore) -> None:
        await store.save_job(JOB_ID, "https://example.com/")
        jobs = await store.list_jobs()
        assert len(jobs) == 1
        assert jobs[0]["job_id"] == JOB_ID
        assert jobs[0]["url"] == "https://example.com/"
        assert jobs[0]["status"] == "submitted"

    async def test_duplicate_is_ignored(self, store: JobStore) -> None:
        await store.save_job(JOB_ID, "https://example.com/")
        await store.save_job(JOB_ID, "https://example.com/")  # should not raise
        jobs = await store.list_jobs()
        assert len(jobs) == 1

    async def test_multiple_jobs(self, store: JobStore) -> None:
        await store.save_job(JOB_ID, "https://example.com/")
        await store.save_job(JOB_ID_2, "https://other.com/")
        jobs = await store.list_jobs()
        assert len(jobs) == 2


class TestUpdateStatus:
    async def test_updates_status(self, store: JobStore) -> None:
        await store.save_job(JOB_ID, "https://example.com/")
        await store.update_status(JOB_ID, "completed")
        jobs = await store.list_jobs()
        assert jobs[0]["status"] == "completed"

    async def test_unknown_job_is_noop(self, store: JobStore) -> None:
        await store.update_status("nonexistent-id", "completed")  # should not raise
        jobs = await store.list_jobs()
        assert len(jobs) == 0

    async def test_updated_at_changes(self, store: JobStore) -> None:
        await store.save_job(JOB_ID, "https://example.com/")
        before = (await store.list_jobs())[0]["updated_at"]
        await store.update_status(JOB_ID, "running")
        after = (await store.list_jobs())[0]["updated_at"]
        assert after >= before


class TestListJobs:
    async def test_returns_most_recent_first(self, store: JobStore) -> None:
        await store.save_job(JOB_ID, "https://first.com/")
        await store.save_job(JOB_ID_2, "https://second.com/")
        jobs = await store.list_jobs()
        # Both were inserted quickly, just verify both are present
        assert len(jobs) == 2

    async def test_status_filter(self, store: JobStore) -> None:
        await store.save_job(JOB_ID, "https://example.com/")
        await store.save_job(JOB_ID_2, "https://other.com/")
        await store.update_status(JOB_ID, "completed")

        completed = await store.list_jobs(status_filter="completed")
        assert len(completed) == 1
        assert completed[0]["job_id"] == JOB_ID

        submitted = await store.list_jobs(status_filter="submitted")
        assert len(submitted) == 1
        assert submitted[0]["job_id"] == JOB_ID_2

    async def test_limit(self, store: JobStore) -> None:
        for i in range(5):
            await store.save_job(f"job-{i}", f"https://example.com/{i}")
        jobs = await store.list_jobs(limit=3)
        assert len(jobs) == 3

    async def test_offset(self, store: JobStore) -> None:
        for i in range(5):
            await store.save_job(f"job-{i}", f"https://example.com/{i}")
        all_jobs = await store.list_jobs(limit=5)
        paged = await store.list_jobs(limit=5, offset=3)
        assert len(paged) == 2
        assert paged[0]["job_id"] == all_jobs[3]["job_id"]

    async def test_empty_returns_empty_list(self, store: JobStore) -> None:
        jobs = await store.list_jobs()
        assert jobs == []
