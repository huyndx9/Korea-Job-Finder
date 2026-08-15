"""Filtering, sorting and pagination over stored jobs (GET /api/jobs)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Job

SORT_OPTIONS = ("latest", "oldest", "salary_desc", "salary_asc")


@dataclass
class JobFilters:
    keywords: list[str] | None = None
    sources: list[str] | None = None
    locations: list[str] | None = None
    employment_types: list[str] | None = None
    experiences: list[str] | None = None
    sort: str = "latest"
    page: int = 1
    limit: int = 20


def _base_query(filters: JobFilters):
    stmt = select(Job)

    keywords = [k.strip() for k in (filters.keywords or []) if k and k.strip()]
    if keywords:
        # a job matches if ANY keyword hits any of its text fields
        stmt = stmt.where(
            or_(
                *[
                    or_(
                        Job.title.like(f"%{k}%"),
                        Job.company.like(f"%{k}%"),
                        Job.description.like(f"%{k}%"),
                        Job.keywords.like(f"%{k}%"),          # the posting's own keywords
                        Job.matched_keywords.like(f"%{k}%"),  # what we searched to find it
                    )
                    for k in keywords
                ]
            )
        )
    if filters.sources:
        stmt = stmt.where(Job.source.in_(filters.sources))
    if filters.locations:
        stmt = stmt.where(Job.location_region.in_(filters.locations))
    if filters.employment_types:
        stmt = stmt.where(Job.employment_type.in_(filters.employment_types))
    if filters.experiences:
        stmt = stmt.where(Job.experience.in_(filters.experiences))
    return stmt


def _apply_sort(stmt, sort: str):
    # Demo rows always rank below real postings, whatever the sort - otherwise a
    # source standing in with mock data can bury the real results.
    real_first = Job.is_mock.asc()

    if sort == "oldest":
        # NULL dates last in both directions, so undated rows never lead the list
        return stmt.order_by(real_first, Job.posted_at.is_(None), Job.posted_at.asc(), Job.id.asc())
    if sort == "salary_desc":
        return stmt.order_by(real_first, Job.salary_value.is_(None), Job.salary_value.desc(), Job.id.desc())
    if sort == "salary_asc":
        return stmt.order_by(real_first, Job.salary_value.is_(None), Job.salary_value.asc(), Job.id.asc())
    return stmt.order_by(real_first, Job.posted_at.is_(None), Job.posted_at.desc(), Job.id.desc())


def query_jobs(db: Session, filters: JobFilters) -> tuple[list[Job], int]:
    """Return ``(page_of_jobs, total_matching)``."""
    stmt = _base_query(filters)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    page = max(1, filters.page)
    limit = max(1, min(filters.limit, 100))
    rows = db.scalars(
        _apply_sort(stmt, filters.sort).offset((page - 1) * limit).limit(limit)
    ).all()
    return list(rows), total


def paginate(jobs: list[Job], page: int, limit: int) -> list[Job]:
    """Same pagination maths for an in-memory list (used by POST /api/search)."""
    page = max(1, page)
    limit = max(1, min(limit, 100))
    return jobs[(page - 1) * limit : (page - 1) * limit + limit]


def sort_jobs(jobs: list[Job], sort: str) -> list[Job]:
    """In-memory equivalent of _apply_sort for a freshly collected result set."""
    real_first = lambda job: bool(job.is_mock)  # noqa: E731 - False (real) sorts before True

    if sort == "salary_desc":
        return sorted(jobs, key=lambda j: (real_first(j), j.salary_value is None, -(j.salary_value or 0)))
    if sort == "salary_asc":
        return sorted(jobs, key=lambda j: (real_first(j), j.salary_value is None, j.salary_value or 0))
    # undated postings always sink to the bottom, whichever direction we sort
    if sort == "oldest":
        return sorted(
            jobs,
            key=lambda j: (real_first(j), j.posted_at is None, j.posted_at.timestamp() if j.posted_at else 0.0),
        )
    # "latest": negate the timestamp instead of reverse=True, so the real-first
    # and nulls-last flags keep pointing the same way
    return sorted(
        jobs,
        key=lambda j: (real_first(j), j.posted_at is None, -(j.posted_at.timestamp() if j.posted_at else 0.0)),
    )
