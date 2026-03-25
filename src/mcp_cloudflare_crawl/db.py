"""
SQLite-backed job store for persisting Cloudflare crawl job IDs.

This module is self-contained: it has no dependency on server.py or
cloudflare_client.py. All database logic lives here.

Usage:
    from mcp_cloudflare_crawl.db import JobStore

    store = JobStore("/path/to/jobs.db")
    await store.init()

    await store.save_job("job-uuid", "https://example.com/")
    await store.update_status("job-uuid", "completed")
    jobs = await store.list_jobs()
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

import aiosqlite

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id     TEXT PRIMARY KEY,
    url        TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'submitted',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status);
"""


class JobRecord(TypedDict):
    job_id: str
    url: str
    status: str
    created_at: str
    updated_at: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    """Async SQLite store for crawl job records."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)

    async def init(self) -> None:
        """Create the database file and table if they don't exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute(CREATE_TABLE_SQL)
            await conn.execute(CREATE_INDEX_SQL)
            await conn.commit()

    async def save_job(self, job_id: str, url: str) -> None:
        """Insert a new job. Silently ignored if job_id already exists."""
        now = _now()
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute(
                """
                INSERT OR IGNORE INTO jobs (job_id, url, status, created_at, updated_at)
                VALUES (?, ?, 'submitted', ?, ?)
                """,
                (job_id, url, now, now),
            )
            await conn.commit()

    async def update_status(self, job_id: str, status: str) -> None:
        """Update the status of an existing job. No-op if job_id is unknown."""
        now = _now()
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE job_id = ?",
                (status, now, job_id),
            )
            await conn.commit()

    async def list_jobs(
        self,
        status_filter: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[JobRecord]:
        """Return a list of job records, ordered by most recently created first."""
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            if status_filter:
                cursor = await conn.execute(
                    """
                    SELECT job_id, url, status, created_at, updated_at
                    FROM jobs
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (status_filter, limit, offset),
                )
            else:
                cursor = await conn.execute(
                    """
                    SELECT job_id, url, status, created_at, updated_at
                    FROM jobs
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )
            rows = await cursor.fetchall()
            return [
                JobRecord(
                    job_id=row["job_id"],
                    url=row["url"],
                    status=row["status"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]
