"""Transaction-local crawl run lifecycle helpers."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, cast

from sqlalchemy import update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from political_archive.models import CrawlRun, CrawlRunStatus


class CrawlCounter(StrEnum):
    DISCOVERED = "discovered_count"
    DOWNLOADED = "downloaded_count"
    PARSED = "parsed_count"
    FAILED = "failed_count"


_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key)\s*[=:]\s*([^\s,;]+)"
)
_URL_CREDENTIALS = re.compile(r"(?i)(https?://)([^/@\s]+)@")


def sanitize_error_summary(error: str, limit: int = 2000) -> str:
    """Remove common credentials before an error is stored in the database."""
    safe = _SECRET_ASSIGNMENT.sub(r"\1=<redacted>", str(error))
    safe = _URL_CREDENTIALS.sub(r"\1<redacted>@", safe)
    return safe[:limit]


def start_crawl_run(session: Session, source_id: int) -> CrawlRun:
    """Insert a RUNNING crawl row; the caller owns the surrounding transaction."""
    run = CrawlRun(source_id=source_id, status=CrawlRunStatus.RUNNING)
    session.add(run)
    session.flush()
    return run


def increment_counter(
    session: Session,
    crawl_run_id: int,
    counter: CrawlCounter,
    amount: int = 1,
) -> None:
    """Atomically increment one nonnegative crawl counter."""
    if amount < 0:
        raise ValueError("counter increment must be nonnegative")
    result = cast(
        CursorResult[Any],
        session.execute(
            update(CrawlRun)
            .where(
                CrawlRun.id == crawl_run_id, CrawlRun.status == CrawlRunStatus.RUNNING
            )
            .values({counter.value: getattr(CrawlRun, counter.value) + amount})
        ),
    )
    if result.rowcount != 1:
        raise LookupError(
            f"crawl run {crawl_run_id} does not exist or is already terminal"
        )


def _finish(
    session: Session,
    crawl_run_id: int,
    status: CrawlRunStatus,
    error_summary: str | None = None,
) -> CrawlRun:
    run = session.get(CrawlRun, crawl_run_id)
    if run is None:
        raise LookupError(f"crawl run not found: {crawl_run_id}")
    if run.status != CrawlRunStatus.RUNNING:
        raise ValueError("crawl run is already in a terminal state")
    run.status = status
    run.finished_at = datetime.now(UTC)
    if error_summary:
        run.error_summary = sanitize_error_summary(error_summary)
    session.flush()
    return run


def finish_crawl_run(
    session: Session,
    crawl_run_id: int,
    status: CrawlRunStatus = CrawlRunStatus.SUCCEEDED,
) -> CrawlRun:
    """Finish a run with SUCCEEDED or PARTIAL and a UTC timestamp."""
    if status not in (CrawlRunStatus.SUCCEEDED, CrawlRunStatus.PARTIAL):
        raise ValueError("finish status must be SUCCEEDED or PARTIAL")
    return _finish(session, crawl_run_id, status)


def fail_crawl_run(session: Session, crawl_run_id: int, error: str) -> CrawlRun:
    """Mark a run failed and retain only a redacted error summary."""
    return _finish(session, crawl_run_id, CrawlRunStatus.FAILED, error)


__all__ = [
    "CrawlCounter",
    "fail_crawl_run",
    "finish_crawl_run",
    "increment_counter",
    "sanitize_error_summary",
    "start_crawl_run",
]
