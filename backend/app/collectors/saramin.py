"""사람인 (Saramin) - official Open API.

Spec: https://oapi.saramin.co.kr/guide/job-search

    GET https://oapi.saramin.co.kr/job-search?access-key=...&keywords=...
    Accept: application/json

The key comes from ``SARAMIN_API_KEY`` and is never hard-coded. Without it the
collector reports ``not_configured`` instead of falling back to anything.

Note on ``start``: the official guide defines it as a zero-based *page number*
(used together with ``count``), NOT a record offset - see ``page_to_start``.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.collectors.base import CollectorError, JobCollector, NormalizedJob, SourceStatus
from app.config import settings
from app.services.normalize_service import (
    normalize_employment_type,
    normalize_experience,
    normalize_region,
    parse_deadline,
    parse_posted_at,
    parse_salary,
)
from app.utils.text import clean_text

logger = logging.getLogger(__name__)

API_URL = "https://oapi.saramin.co.kr/job-search"

#: Saramin caps a page at 110 rows.
MAX_COUNT = 110

#: Every filter the endpoint accepts. Anything outside this set is dropped
#: rather than forwarded, so a typo cannot turn into an "invalid parameter".
SUPPORTED_PARAMS: frozenset[str] = frozenset(
    {
        "keywords",
        "bbs_gb",
        "stock",
        "sr",
        "loc_cd",
        "loc_mcd",
        "loc_bcd",
        "ind_cd",
        "job_mid_cd",
        "job_cd",
        "job_type",
        "edu_lv",
        "fields",
        "published",
        "published_min",
        "published_max",
        "updated",
        "updated_min",
        "updated_max",
        "deadline",
        "start",
        "count",
        "sort",
    }
)

#: pd = newest posting first (default), pa = oldest, ud/ua = modified,
#: da/dd = deadline, rc = most viewed, ac = most applied.
SORT_OPTIONS: frozenset[str] = frozenset({"pd", "pa", "ud", "ua", "da", "dd", "rc", "ac"})
DEFAULT_SORT = "pd"

#: documented error codes -> our internal status
ERROR_CODES: dict[int, tuple[SourceStatus, str]] = {
    1: (SourceStatus.NOT_CONFIGURED, "access-key was not sent"),
    2: (SourceStatus.INVALID_KEY, "invalid access-key - check SARAMIN_API_KEY"),
    3: (SourceStatus.INVALID_REQUEST, "invalid request parameter"),
    4: (SourceStatus.RATE_LIMITED, "daily request limit exceeded"),
    99: (SourceStatus.API_ERROR, "Saramin server error"),
}


def page_to_start(page: int, limit: int) -> int:
    """Frontend page/limit -> Saramin ``start``.

    The guide defines ``start`` as a zero-based page index, so with
    ``count == limit`` the conversion is ``page - 1`` - not ``(page-1)*limit``,
    which would skip whole blocks of results (page 2 of 20 would land on
    records 401-420).
    """
    return max(0, page - 1)


class SaraminCollector(JobCollector):
    name = "saramin"
    label = "사람인"
    site_url = "https://www.saramin.co.kr"

    @property
    def unavailable_reason(self) -> str | None:  # type: ignore[override]
        if not settings.saramin_api_key:
            return "SARAMIN_API_KEY is not set (free key: https://oapi.saramin.co.kr/)"
        return None

    def unavailable_status(self) -> SourceStatus:
        return SourceStatus.NOT_CONFIGURED

    # ---------------------------------------------------------------- search

    def build_params(
        self,
        keyword: str,
        limit: int = 50,
        start: int = 0,
        sort: str = DEFAULT_SORT,
        **filters: Any,
    ) -> dict[str, Any]:
        """Assemble the query string. Kept public so tests can assert on it."""
        params: dict[str, Any] = {
            "access-key": settings.saramin_api_key,
            "keywords": keyword,
            "start": max(0, int(start)),
            "count": max(1, min(int(limit), MAX_COUNT)),
            "sort": sort if sort in SORT_OPTIONS else DEFAULT_SORT,
            # ask for the optional blocks we normalize
            "fields": "posting-date,expiration-date,keyword-code,count",
        }

        for key, value in filters.items():
            if value in (None, "", []):
                continue
            if key not in SUPPORTED_PARAMS:
                logger.warning("saramin: ignoring unsupported parameter %r", key)
                continue
            # every multi-value filter is comma separated
            params[key] = ",".join(str(v) for v in value) if isinstance(value, (list, tuple, set)) else value
        return params

    def search(self, keyword: str, limit: int = 50, **options: Any) -> list[dict[str, Any]]:
        params = self.build_params(keyword, limit=limit, **options)

        try:
            with self._client() as client:
                response = client.get(API_URL, params=params, headers={"Accept": "application/json"})
        except httpx.HTTPError as exc:
            raise CollectorError(SourceStatus.ERROR, f"request failed: {exc}") from exc

        # Saramin reports errors in the body, sometimes with a 200 status
        try:
            payload = response.json()
        except ValueError as exc:
            raise CollectorError(
                SourceStatus.API_ERROR,
                f"expected JSON, got {response.headers.get('content-type', 'unknown')} (HTTP {response.status_code})",
            ) from exc

        if not isinstance(payload, dict):
            raise CollectorError(
                SourceStatus.API_ERROR,
                f"expected a JSON object, got {type(payload).__name__} (HTTP {response.status_code})",
            )

        self._raise_for_api_error(payload, response.status_code)

        jobs = payload.get("jobs")
        if not isinstance(jobs, dict):
            raise CollectorError(SourceStatus.API_ERROR, "unexpected response shape: no 'jobs' object")

        rows = jobs.get("job") or []
        if isinstance(rows, dict):  # the API collapses a single result to an object
            rows = [rows]
        if not isinstance(rows, list):
            raise CollectorError(SourceStatus.API_ERROR, "unexpected response shape: 'job' is not a list")
        return rows

    @staticmethod
    def _raise_for_api_error(payload: Any, status_code: int) -> None:
        if isinstance(payload, dict) and "code" in payload and "jobs" not in payload:
            try:
                code = int(payload["code"])
            except (TypeError, ValueError):
                code = -1
            status, description = ERROR_CODES.get(code, (SourceStatus.API_ERROR, "unknown API error"))
            detail = clean_text(payload.get("message")) or description
            raise CollectorError(status, f"[{code}] {detail}")

        if status_code >= 400:
            raise CollectorError(SourceStatus.API_ERROR, f"HTTP {status_code}")

    # ------------------------------------------------------------- normalize

    def normalize(self, raw_job: dict[str, Any]) -> NormalizedJob | None:
        position = raw_job.get("position") or {}
        title = clean_text(position.get("title"))
        url = raw_job.get("url")
        if not title or not url:
            return None

        company = clean_text(((raw_job.get("company") or {}).get("detail") or {}).get("name"))
        location = clean_text(self._named(position.get("location")))
        salary = raw_job.get("salary") or {}
        salary_text, salary_value = parse_salary(self._named(salary))

        experience_name = self._named(position.get("experience-level"))
        education = clean_text(self._named(position.get("required-education-level")))

        description = clean_text(
            self._named(position.get("job-code"))
            or self._named(position.get("job-mid-code"))
            or self._named(position.get("industry")),
            max_length=500,
        )

        return NormalizedJob(
            source=self.name,
            source_job_id=str(raw_job["id"]) if raw_job.get("id") is not None else None,
            title=title,
            company=company or "회사명 비공개",
            location=location,
            location_region=normalize_region(location),
            salary=salary_text,
            salary_code=clean_text(salary.get("code")) if isinstance(salary, dict) else None,
            salary_value=salary_value,
            employment_type=normalize_employment_type(self._named(position.get("job-type"))),
            experience=normalize_experience(experience_name),
            education=education,
            description=description,
            url=url,
            posted_at=parse_posted_at(
                raw_job.get("posting-timestamp") or raw_job.get("posting-date")
            ),
            deadline=parse_deadline(
                raw_job.get("expiration-timestamp") or raw_job.get("expiration-date")
            ),
            keywords=clean_text(raw_job.get("keyword")),
            is_active=str(raw_job.get("active", 1)) == "1",
        )

    @staticmethod
    def _named(node: Any) -> str | None:
        """Saramin wraps most values as {"code": .., "name": ..}."""
        if isinstance(node, dict):
            return node.get("name")
        return node if isinstance(node, str) else None
