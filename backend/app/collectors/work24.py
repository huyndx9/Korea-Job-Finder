"""워크24 / 고용24 (Work24) - the government's official Open API.

Free key from https://www.work24.go.kr (오픈API 신청). Put it in .env as
``WORK24_API_KEY``. The API answers XML. Without a key the collector is
unavailable - the public site is JS-rendered and we do not scrape around it.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from app.collectors.base import JobCollector, NormalizedJob, SourceStatus
from app.config import settings
from app.services.normalize_service import (
    normalize_employment_type,
    normalize_experience,
    normalize_region,
    parse_posted_at,
    parse_salary,
)
from app.utils.text import clean_text

API_URL = "https://openapi.work.go.kr/opi/opi/opiaEmpInfoSrch/list.do"


class Work24Collector(JobCollector):
    name = "work24"
    label = "워크24"
    site_url = "https://www.work24.go.kr"

    @property
    def unavailable_reason(self) -> str | None:  # type: ignore[override]
        if not settings.work24_api_key:
            return "WORK24_API_KEY is not set (free key: https://www.work24.go.kr open API)"
        return None

    def unavailable_status(self) -> SourceStatus:
        return SourceStatus.NOT_CONFIGURED

    def search(self, keyword: str, limit: int = 50, **_options: Any) -> list[dict[str, Any]]:
        params = {
            "authKey": settings.work24_api_key,
            "callTp": "L",       # list
            "returnType": "XML",
            "startPage": 1,
            "display": min(limit, 100),
            "keyword": keyword,
            "sortOrderBy": "DESC",
            "sortField": "DATE",
        }
        with self._client() as client:
            response = client.get(API_URL, params=params)
            response.raise_for_status()
            text = response.text

        root = ET.fromstring(text)
        rows: list[dict[str, Any]] = []
        for item in root.iter("wanted"):
            rows.append({child.tag: (child.text or "").strip() for child in item})
        return rows[:limit]

    def normalize(self, raw_job: dict[str, Any]) -> NormalizedJob | None:
        title = clean_text(raw_job.get("title"))
        url = raw_job.get("wantedInfoUrl") or raw_job.get("wantedMobileInfoUrl")
        if not title or not url:
            return None

        location = clean_text(raw_job.get("region"))
        salary_text, salary_value = parse_salary(raw_job.get("sal") or raw_job.get("salTpNm"))

        return NormalizedJob(
            source=self.name,
            source_job_id=clean_text(raw_job.get("wantedAuthNo")),
            title=title,
            company=clean_text(raw_job.get("company")) or "회사명 비공개",
            location=location,
            location_region=normalize_region(location),
            salary=salary_text,
            salary_value=salary_value,
            employment_type=normalize_employment_type(raw_job.get("holidayTpNm") or raw_job.get("empTpNm")),
            experience=normalize_experience(raw_job.get("career")),
            description=clean_text(raw_job.get("jobsCdKorNm") or raw_job.get("indTpNm"), 500),
            url=url,
            posted_at=parse_posted_at(raw_job.get("regDt")),
        )
