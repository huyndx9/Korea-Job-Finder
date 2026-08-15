"""API request / response shapes."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    source_job_id: str | None = None

    title: str
    company: str

    location: str | None = None
    location_region: str | None = None
    salary: str | None = None
    salary_code: str | None = None
    salary_value: int | None = None
    employment_type: str | None = None
    experience: str | None = None
    education: str | None = None

    description: str | None = None
    url: str

    posted_at: datetime | None = None
    deadline: datetime | None = None
    collected_at: datetime

    keywords: str | None = None
    is_active: bool = True
    is_mock: bool = False


class SourceOut(BaseModel):
    """One entry of GET /api/sources (keyed by source name)."""

    name: str
    label: str
    site_url: str
    default: bool
    available: bool
    custom: bool = False
    # connected | not_configured | invalid_key | invalid_request | rate_limited
    # | api_error | error | timeout | unavailable | demo | idle
    status: str
    message: str | None = None
    last_success: str | None = None
    last_checked: str | None = None
    last_result_count: int = 0


class CollectorStatusOut(BaseModel):
    source: str
    label: str
    ok: bool
    status: str
    count: int
    elapsed_ms: int
    is_mock: bool
    error: str | None = None


class SearchRequest(BaseModel):
    keywords: list[str] = Field(default_factory=list, description="예: ['베트남어', '통역']")
    sources: list[str] | None = None
    page: int = 1
    limit: int = 20
    sort: str = "latest"


class PageMeta(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int


class JobListResponse(BaseModel):
    jobs: list[JobOut]
    pagination: PageMeta


class SearchResponse(BaseModel):
    keywords: list[str]
    jobs: list[JobOut]
    pagination: PageMeta
    sources: list[CollectorStatusOut]
    elapsed_ms: int
    duplicates_removed: int


class HealthResponse(BaseModel):
    status: str
    app: str
    database: str
    jobs_stored: int
    demo_mode: bool
