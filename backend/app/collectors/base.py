"""Collector interface.

Every job site is an independent collector. The rules:

*   ``search()``      -> hits the site, returns a list of RAW dicts (whatever the site gives us)
*   ``normalize()``   -> turns one raw dict into a NormalizedJob (or None if unusable)
*   ``is_available()``-> can this collector run right now? (e.g. is the API key configured)

A collector must never raise out of ``collect()`` in a way that kills the whole search -
the search service catches everything, but collectors are expected to fail politely.

We never work around CAPTCHAs, logins, rate limits or anti-bot measures. A source that
cannot be read with a plain, well-identified HTTP request is reported as unavailable.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class SourceStatus(str, Enum):
    """Why a source did or did not deliver. Surfaced verbatim to the UI."""

    CONNECTED = "connected"          # ran and returned data
    NOT_CONFIGURED = "not_configured"  # needs an API key we do not have
    INVALID_KEY = "invalid_key"
    INVALID_REQUEST = "invalid_request"
    RATE_LIMITED = "rate_limited"
    API_ERROR = "api_error"          # the source answered with an error
    ERROR = "error"                  # network / parse failure on our side
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"      # cannot be collected legitimately at all
    DEMO = "demo"                    # sample data, only when DEMO_MODE=true
    IDLE = "idle"                    # not searched yet in this process


class CollectorError(Exception):
    """A failure a collector can describe precisely."""

    def __init__(self, status: SourceStatus, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass
class NormalizedJob:
    """The common shape every source is mapped onto."""

    source: str
    title: str
    company: str
    url: str
    source_job_id: str | None = None
    location: str | None = None
    location_region: str | None = None
    salary: str | None = None
    salary_code: str | None = None
    salary_value: int | None = None
    employment_type: str | None = None
    experience: str | None = None
    education: str | None = None
    description: str | None = None
    posted_at: datetime | None = None
    deadline: datetime | None = None
    keywords: str | None = None      # the source's own keyword list, if it has one
    is_active: bool = True
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_mock: bool = False
    fingerprint: str = ""

    def is_valid(self) -> bool:
        """A posting is only usable if we can show it and link to it."""
        return bool(self.title and self.title.strip()) and bool(self.url and self.url.startswith("http"))


@dataclass
class CollectorResult:
    """Per-source outcome of one search, surfaced to the UI."""

    source: str
    label: str
    ok: bool
    status: SourceStatus = SourceStatus.CONNECTED
    count: int = 0
    error: str | None = None
    elapsed_ms: int = 0
    is_mock: bool = False
    jobs: list[NormalizedJob] = field(default_factory=list)


class JobCollector(ABC):
    """Base class for every source."""

    name: str = "base"
    label: str = "Base"
    site_url: str = ""
    # Set when the source cannot be collected legitimately (JS-only, ToS, anti-bot).
    unavailable_reason: str | None = None

    # ---- interface -------------------------------------------------------

    @abstractmethod
    def search(self, keyword: str, limit: int = 50, **options: Any) -> list[dict[str, Any]]:
        """Return raw, source-shaped results for one keyword."""

    @abstractmethod
    def normalize(self, raw_job: dict[str, Any]) -> NormalizedJob | None:
        """Map one raw result onto NormalizedJob. Return None to drop it."""

    def is_available(self) -> bool:
        """False when the source needs configuration we do not have."""
        return self.unavailable_reason is None

    def unavailable_status(self) -> SourceStatus:
        """Which flavour of unavailable this is - overridden by keyed sources."""
        return SourceStatus.UNAVAILABLE

    # ---- template method used by the search service ----------------------

    def collect(self, keyword: str, limit: int = 50, **options: Any) -> list[NormalizedJob]:
        raw_jobs = self.search(keyword, limit=limit, **options)
        jobs: list[NormalizedJob] = []
        for raw in raw_jobs:
            try:
                job = self.normalize(raw)
            except Exception:  # one bad row must not lose the rest of the page
                logger.warning("%s: failed to normalize a row", self.name, exc_info=True)
                continue
            if job is not None and job.is_valid():
                jobs.append(job)
        return jobs

    # ---- shared helpers --------------------------------------------------

    def _client(self) -> httpx.Client:
        return httpx.Client(
            timeout=settings.request_timeout,
            follow_redirects=True,
            headers={
                "User-Agent": settings.user_agent,
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            },
        )
