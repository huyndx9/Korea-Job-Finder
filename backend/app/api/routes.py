"""HTTP API.

    GET  /api/health
    GET  /api/sources
    POST /api/search
    GET  /api/jobs
    GET  /api/jobs/{id}
"""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.collectors import COLLECTOR_CLASSES, DEFAULT_SOURCES, load_custom_sources
from app.collectors.custom import CustomCollector
from app.collectors.base import SourceStatus
from app.config import settings
from app.database import get_db
from app.models import Job
from app.services import source_status
from app.schemas import (
    CollectorStatusOut,
    HealthResponse,
    JobListResponse,
    JobOut,
    PageMeta,
    SearchRequest,
    SearchResponse,
    SourceOut,
)
from app.services.job_query import SORT_OPTIONS, JobFilters, paginate, query_jobs, sort_jobs
from app.services.search_service import run_search

router = APIRouter(prefix="/api")


def _page_meta(page: int, limit: int, total: int) -> PageMeta:
    limit = max(1, min(limit, 100))
    return PageMeta(
        page=max(1, page),
        limit=limit,
        total=total,
        total_pages=max(1, math.ceil(total / limit)) if total else 0,
    )


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    try:
        stored = db.scalar(select(func.count()).select_from(Job)) or 0
        database = "ok"
    except Exception:  # noqa: BLE001 - health must answer even with a broken DB
        stored, database = 0, "error"
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        database=database,
        jobs_stored=stored,
        demo_mode=settings.demo_mode,
    )


@router.get("/sources", response_model=dict[str, SourceOut])
def list_sources(db: Session = Depends(get_db)) -> dict[str, SourceOut]:
    """Per-source configuration + live health, keyed by source name.

    Built-in collectors first, then anything the user added by hand.
    """
    sources: dict[str, SourceOut] = {}
    collectors = [cls() for cls in COLLECTOR_CLASSES]
    collectors += [CustomCollector(config) for config in load_custom_sources(db)]

    for collector in collectors:
        observed = source_status.get(collector.name)

        if not collector.is_available():
            # configuration beats anything we observed earlier
            status = collector.unavailable_status()
            message = collector.unavailable_reason
        elif observed is not None:
            status, message = observed.status, observed.message
        else:
            status, message = SourceStatus.IDLE, "not searched yet"

        sources[collector.name] = SourceOut(
            name=collector.name,
            label=collector.label,
            site_url=collector.site_url,
            default=collector.name in DEFAULT_SOURCES,
            available=collector.is_available(),
            custom=getattr(collector, "is_custom", False),
            status=status.value,
            message=message,
            last_success=observed.last_success if observed else None,
            last_checked=observed.last_checked if observed else None,
            last_result_count=observed.last_result_count if observed else 0,
        )
    return sources


@router.post("/search", response_model=SearchResponse)
async def search(payload: SearchRequest, db: Session = Depends(get_db)) -> SearchResponse:
    keywords = [k.strip() for k in payload.keywords if k and k.strip()]
    if not keywords:
        raise HTTPException(status_code=400, detail="키워드를 입력해 주세요 (keywords is required)")

    sort = payload.sort if payload.sort in SORT_OPTIONS else "latest"
    outcome = await run_search(db, keywords, payload.sources)

    ordered = sort_jobs(outcome.jobs, sort)
    page_rows = paginate(ordered, payload.page, payload.limit)

    return SearchResponse(
        keywords=keywords,
        jobs=[JobOut.model_validate(job) for job in page_rows],
        pagination=_page_meta(payload.page, payload.limit, len(ordered)),
        sources=[
            CollectorStatusOut(
                source=r.source,
                label=r.label,
                ok=r.ok,
                status=r.status.value,
                count=r.count,
                elapsed_ms=r.elapsed_ms,
                is_mock=r.is_mock,
                error=r.error,
            )
            for r in outcome.results
        ],
        elapsed_ms=outcome.elapsed_ms,
        duplicates_removed=outcome.duplicates_removed,
    )


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    keyword: list[str] | None = Query(default=None, description="repeatable; matches ANY"),
    source: list[str] | None = Query(default=None),
    location: list[str] | None = Query(default=None),
    employment_type: list[str] | None = Query(default=None),
    experience: list[str] | None = Query(default=None),
    sort: str = "latest",
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db),
) -> JobListResponse:
    filters = JobFilters(
        keywords=keyword,
        sources=source,
        locations=location,
        employment_types=employment_type,
        experiences=experience,
        sort=sort if sort in SORT_OPTIONS else "latest",
        page=page,
        limit=limit,
    )
    rows, total = query_jobs(db, filters)
    return JobListResponse(
        jobs=[JobOut.model_validate(row) for row in rows],
        pagination=_page_meta(page, limit, total),
    )


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobOut:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobOut.model_validate(job)
