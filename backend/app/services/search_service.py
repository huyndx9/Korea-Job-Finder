"""Search orchestration: fan out to collectors, normalize, dedupe, store, return.

    keywords ─┐
              ├─> collector A ─┐
              ├─> collector B ─┼─> normalize ─> validate ─> dedupe ─> SQLite ─> results
              └─> collector C ─┘

Every collector runs in its own thread with its own timeout, and every failure is
caught and recorded. One dead source can never fail the request.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.collectors import DEFAULT_SOURCES, JobCollector, MockJobCollector, build_collectors
from app.collectors.base import CollectorError, CollectorResult, NormalizedJob, SourceStatus
from app.config import settings
from app.models import Job
from app.services import source_status
from app.services.dedup_service import deduplicate, make_fingerprint

logger = logging.getLogger(__name__)


class SearchOutcome:
    """What one POST /api/search produced."""

    def __init__(
        self,
        jobs: list[Job],
        results: list[CollectorResult],
        elapsed_ms: int,
        duplicates_removed: int,
    ) -> None:
        self.jobs = jobs
        self.results = results
        self.elapsed_ms = elapsed_ms
        self.duplicates_removed = duplicates_removed


# ---------------------------------------------------------------- collection


def _collect_sync(collector: JobCollector, keywords: list[str], limit: int) -> list[NormalizedJob]:
    """Run one collector over every keyword. Blocking - called in a thread."""
    jobs: list[NormalizedJob] = []
    for keyword in keywords:
        jobs.extend(collector.collect(keyword, limit=limit))
    return jobs


def _mock_stand_in(collector: JobCollector, keywords: list[str], limit: int) -> list[NormalizedJob]:
    mock = MockJobCollector(as_source=collector.name, as_label=collector.label)
    return _collect_sync(mock, keywords, limit)


async def _run_collector(collector: JobCollector, keywords: list[str], limit: int) -> CollectorResult:
    started = time.perf_counter()

    def finish(
        status: SourceStatus,
        jobs: list[NormalizedJob],
        error: str | None,
        is_mock: bool = False,
    ) -> CollectorResult:
        source_status.record(collector.name, status, error, len(jobs))
        return CollectorResult(
            source=collector.name,
            label=collector.label,
            ok=status in (SourceStatus.CONNECTED, SourceStatus.DEMO),
            status=status,
            count=len(jobs),
            error=error,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            is_mock=is_mock,
            jobs=jobs,
        )

    def failed(status: SourceStatus, message: str) -> CollectorResult:
        """Report the real reason. Sample data only if DEMO_MODE is on."""
        if settings.demo_mode:
            return finish(SourceStatus.DEMO, _mock_stand_in(collector, keywords, limit), message, is_mock=True)
        return finish(status, [], message)

    # 1. not configured / not collectable at all
    if not collector.is_available():
        reason = collector.unavailable_reason or "source unavailable"
        logger.warning(
            "collector unavailable | source=%s | status=%s | reason=%s | at=%s",
            collector.name, collector.unavailable_status().value, reason,
            datetime.now(timezone.utc).isoformat(),
        )
        return failed(collector.unavailable_status(), reason)

    # 2. run it, guarding against hangs and anything the site throws at us
    try:
        jobs = await asyncio.wait_for(
            asyncio.to_thread(_collect_sync, collector, keywords, limit),
            timeout=settings.collector_timeout,
        )
        return finish(SourceStatus.CONNECTED, jobs, None)

    except asyncio.TimeoutError:
        message = f"timed out after {settings.collector_timeout:.0f}s"
        logger.error(
            "collector timeout | source=%s | error=%s | at=%s",
            collector.name, message, datetime.now(timezone.utc).isoformat(),
        )
        return failed(SourceStatus.TIMEOUT, message)

    except CollectorError as exc:
        # the collector knows exactly what went wrong (bad key, rate limit, ...)
        logger.error(
            "collector error | source=%s | status=%s | error=%s | at=%s",
            collector.name, exc.status.value, exc.message,
            datetime.now(timezone.utc).isoformat(),
        )
        return failed(exc.status, exc.message[:300])

    except Exception as exc:  # noqa: BLE001 - a broken source must not break the search
        message = f"{type(exc).__name__}: {exc}"[:300]
        logger.error(
            "collector failed | source=%s | error=%s | at=%s",
            collector.name, message, datetime.now(timezone.utc).isoformat(),
            exc_info=True,
        )
        return failed(SourceStatus.ERROR, message)


# ------------------------------------------------------------------ persistence


def _save_jobs(db: Session, jobs: list[NormalizedJob], keywords: list[str]) -> list[Job]:
    """Insert new postings, refresh ones we have seen before. Keyed on fingerprint.

    Two searches running at once can both read "not present" and then both insert
    the same posting; the UNIQUE index on fingerprint turns the loser into an
    IntegrityError. Retrying once is enough - the second pass sees the row the
    other request committed and takes the update branch.
    """
    if not jobs:
        return []

    for attempt in (1, 2):
        try:
            return _merge_and_commit(db, jobs, keywords)
        except IntegrityError:
            db.rollback()
            if attempt == 2:
                raise
            logger.info("concurrent insert detected, merging again")
    return []


def _merge_and_commit(db: Session, jobs: list[NormalizedJob], keywords: list[str]) -> list[Job]:
    fingerprints = [job.fingerprint for job in jobs]
    existing = {
        row.fingerprint: row
        for row in db.scalars(select(Job).where(Job.fingerprint.in_(fingerprints)))
    }
    keyword_text = ",".join(keywords)
    saved: list[Job] = []

    for job in jobs:
        row = existing.get(job.fingerprint)
        if row is None:
            row = Job(
                source=job.source,
                source_job_id=job.source_job_id,
                title=job.title,
                company=job.company,
                location=job.location,
                location_region=job.location_region,
                salary=job.salary,
                salary_code=job.salary_code,
                salary_value=job.salary_value,
                employment_type=job.employment_type,
                experience=job.experience,
                education=job.education,
                description=job.description,
                url=job.url,
                posted_at=job.posted_at,
                deadline=job.deadline,
                collected_at=job.collected_at.replace(tzinfo=None),
                fingerprint=job.fingerprint,
                keywords=job.keywords,
                matched_keywords=keyword_text,
                is_active=int(job.is_active),
                is_mock=int(job.is_mock),
            )
            db.add(row)
            existing[job.fingerprint] = row
        else:
            # keep the freshest copy of a posting we already know
            row.collected_at = job.collected_at.replace(tzinfo=None)
            row.salary = job.salary or row.salary
            row.salary_code = job.salary_code or row.salary_code
            row.salary_value = job.salary_value or row.salary_value
            row.posted_at = job.posted_at or row.posted_at
            row.deadline = job.deadline or row.deadline
            row.education = job.education or row.education
            row.keywords = job.keywords or row.keywords
            row.is_active = int(job.is_active)
            merged = {k for k in (row.matched_keywords or "").split(",") if k} | set(keywords)
            row.matched_keywords = ",".join(sorted(merged))
        saved.append(row)

    db.commit()
    for row in saved:
        db.refresh(row)
    return saved


# --------------------------------------------------------------------- entry


async def run_search(
    db: Session,
    keywords: list[str],
    sources: list[str] | None = None,
    limit_per_source: int | None = None,
) -> SearchOutcome:
    started = time.perf_counter()
    keywords = [k.strip() for k in keywords if k and k.strip()]
    limit = limit_per_source or settings.max_results_per_collector

    # pass the session so user-added sources join the built-in ones
    registry = build_collectors(db)
    wanted = sources or DEFAULT_SOURCES
    selected = [registry[name] for name in wanted if name in registry]

    if not selected or not keywords:
        return SearchOutcome([], [], int((time.perf_counter() - started) * 1000), 0)

    results = await asyncio.gather(
        *(_run_collector(collector, keywords, limit) for collector in selected)
    )

    collected: list[NormalizedJob] = []
    for result in results:
        for job in result.jobs:
            job.fingerprint = make_fingerprint(job)
        collected.extend(result.jobs)

    unique = deduplicate(collected)
    duplicates_removed = len(collected) - len(unique)
    saved = _save_jobs(db, unique, keywords)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "search done | keywords=%s | sources=%s | collected=%d | unique=%d | %dms",
        keywords, [c.name for c in selected], len(collected), len(unique), elapsed_ms,
    )
    return SearchOutcome(saved, list(results), elapsed_ms, duplicates_removed)
