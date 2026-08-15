"""Manage job sites the user adds by hand.

    GET    /api/sources/custom
    POST   /api/sources/custom
    POST   /api/sources/custom/test     - dry run, saves nothing
    PATCH  /api/sources/custom/{name}
    DELETE /api/sources/custom/{name}
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors.base import CollectorError, SourceStatus
from app.collectors.custom import CustomCollector
from app.database import get_db
from app.models.custom_source import CustomSource
from app.schemas import (
    CustomSourceCreate,
    CustomSourceOut,
    CustomSourceTestRequest,
    CustomSourceTestResponse,
    CustomSourceUpdate,
)
from app.schemas.job import JobOut
from app.utils.url_guard import UnsafeUrlError, validate_search_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sources/custom", tags=["custom sources"])

PREVIEW_LIMIT = 5


def _get_or_404(db: Session, name: str) -> CustomSource:
    source = db.scalar(select(CustomSource).where(CustomSource.name == name))
    if source is None:
        raise HTTPException(status_code=404, detail=f"custom source '{name}' not found")
    return source


@router.get("", response_model=list[CustomSourceOut])
def list_custom_sources(db: Session = Depends(get_db)) -> list[CustomSource]:
    return list(db.scalars(select(CustomSource).order_by(CustomSource.id)))


@router.post("", response_model=CustomSourceOut, status_code=201)
def create_custom_source(
    payload: CustomSourceCreate, db: Session = Depends(get_db)
) -> CustomSource:
    if db.scalar(select(CustomSource).where(CustomSource.name == payload.name)):
        raise HTTPException(status_code=409, detail=f"'{payload.name}' already exists")

    try:
        validate_search_url(payload.search_url)
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    source = CustomSource(**payload.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    logger.info("custom source added | name=%s | url=%s", source.name, source.search_url)
    return source


@router.post("/test", response_model=CustomSourceTestResponse)
def test_custom_source(payload: CustomSourceTestRequest) -> CustomSourceTestResponse:
    """Fetch and parse with a throwaway config so the user can see what they get."""
    data = payload.model_dump()
    keyword = data.pop("keyword") or "베트남어"
    draft = CustomSource(**data)
    collector = CustomCollector(draft)
    requested_url = collector.build_url(keyword)

    try:
        raw_items = collector.search(keyword, limit=PREVIEW_LIMIT)
    except CollectorError as exc:
        return CustomSourceTestResponse(
            ok=False, status=exc.status.value, message=exc.message, requested_url=requested_url
        )
    except Exception as exc:  # noqa: BLE001 - the preview must always answer
        logger.warning("custom source test failed", exc_info=True)
        return CustomSourceTestResponse(
            ok=False,
            status=SourceStatus.ERROR.value,
            message=f"{type(exc).__name__}: {exc}"[:300],
            requested_url=requested_url,
        )

    jobs = []
    for raw in raw_items:
        try:
            job = collector.normalize(raw)
        except Exception:  # noqa: BLE001
            continue
        if job is not None and job.is_valid():
            jobs.append(job)

    if not raw_items:
        message = "요청은 성공했지만 '공고 선택자'와 일치하는 항목이 없습니다."
    elif not jobs:
        message = "항목은 찾았지만 제목/링크를 읽지 못했습니다. 제목·링크 선택자를 확인하세요."
    else:
        message = f"{len(jobs)}개의 공고를 읽었습니다."

    return CustomSourceTestResponse(
        ok=bool(jobs),
        status=SourceStatus.CONNECTED.value if jobs else SourceStatus.INVALID_REQUEST.value,
        message=message,
        requested_url=requested_url,
        items_found=len(raw_items),
        jobs_parsed=len(jobs),
        # preview rows are not saved, so they have no database id
        jobs=[
            JobOut(
                id=0,
                source=job.source,
                source_job_id=job.source_job_id,
                title=job.title,
                company=job.company,
                location=job.location,
                location_region=job.location_region,
                salary=job.salary,
                salary_value=job.salary_value,
                employment_type=job.employment_type,
                experience=job.experience,
                description=job.description,
                url=job.url,
                posted_at=job.posted_at,
                collected_at=job.collected_at,
                keywords=job.keywords,
                is_active=job.is_active,
                is_mock=job.is_mock,
            )
            for job in jobs
        ],
    )


@router.patch("/{name}", response_model=CustomSourceOut)
def update_custom_source(
    name: str, payload: CustomSourceUpdate, db: Session = Depends(get_db)
) -> CustomSource:
    source = _get_or_404(db, name)
    changes = payload.model_dump(exclude_unset=True)

    if "kind" in changes and changes["kind"] not in ("html", "json"):
        raise HTTPException(status_code=400, detail="kind must be 'html' or 'json'")
    if "search_url" in changes and changes["search_url"]:
        try:
            validate_search_url(changes["search_url"])
        except UnsafeUrlError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    for field, value in changes.items():
        setattr(source, field, value)
    db.commit()
    db.refresh(source)
    return source


@router.delete("/{name}", status_code=204)
def delete_custom_source(name: str, db: Session = Depends(get_db)) -> None:
    source = _get_or_404(db, name)
    db.delete(source)
    db.commit()
    logger.info("custom source removed | name=%s", name)
