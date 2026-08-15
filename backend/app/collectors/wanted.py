"""원티드 (Wanted) - the public JSON endpoint its own web client calls.

No key, no login, no anti-bot workaround: the same request the public site makes
when you search. If Wanted changes or blocks the endpoint the collector just
errors and the other sources carry the search.
"""

from __future__ import annotations

from typing import Any

from app.collectors.base import JobCollector, NormalizedJob
from app.services.normalize_service import normalize_region, parse_posted_at, parse_salary
from app.utils.text import clean_text

API_URL = "https://www.wanted.co.kr/api/v4/jobs"
JOB_URL = "https://www.wanted.co.kr/wd/{id}"


class WantedCollector(JobCollector):
    name = "wanted"
    label = "원티드"
    site_url = "https://www.wanted.co.kr"

    def search(self, keyword: str, limit: int = 50, **_options: Any) -> list[dict[str, Any]]:
        params = {
            "country": "kr",
            "job_sort": "job.latest_order",
            "locations": "all",
            "years": "-1",
            "limit": min(limit, 100),
            "offset": 0,
            "query": keyword,
        }
        with self._client() as client:
            response = client.get(
                API_URL,
                params=params,
                headers={"Accept": "application/json", "Referer": self.site_url},
            )
            response.raise_for_status()
            payload = response.json()

        rows = payload.get("data") or []
        return rows if isinstance(rows, list) else []

    @staticmethod
    def _experience(raw_job: dict[str, Any]) -> str | None:
        """Wanted encodes experience as a year range; 0 years means 신입."""
        years_from = raw_job.get("annual_from")
        years_to = raw_job.get("annual_to")
        if years_from is None and years_to is None:
            return None
        if years_from in (None, 0) and (years_to in (None, 0)):
            return "신입"
        if years_from in (None, 0):
            return "경력무관"
        return "경력"

    def normalize(self, raw_job: dict[str, Any]) -> NormalizedJob | None:
        job_id = raw_job.get("id")
        title = clean_text(raw_job.get("position") or raw_job.get("title"))
        if not title or job_id is None:
            return None

        company = clean_text((raw_job.get("company") or {}).get("name"))
        address = raw_job.get("address") or {}
        location = clean_text(
            " ".join(
                part
                for part in (address.get("location"), address.get("district"))
                if part
            )
        )

        # Wanted lists a referral reward, not a salary - only use it when the
        # posting actually carries salary text.
        salary_text, salary_value = parse_salary(raw_job.get("salary") or raw_job.get("annual_salary"))

        return NormalizedJob(
            source=self.name,
            source_job_id=str(job_id),
            title=title,
            company=company or "회사명 비공개",
            location=location,
            location_region=normalize_region(location),
            salary=salary_text,
            salary_value=salary_value,
            # Wanted is a career platform: postings are 정규직 unless stated otherwise
            employment_type="정규직",
            experience=self._experience(raw_job),
            description=clean_text(raw_job.get("category") or raw_job.get("description"), 500),
            url=JOB_URL.format(id=job_id),
            posted_at=parse_posted_at(raw_job.get("confirm_time") or raw_job.get("published_at")),
        )
