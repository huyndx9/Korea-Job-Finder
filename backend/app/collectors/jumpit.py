"""점핏 (Jumpit) - the public JSON endpoint its own web client calls.

Developer-focused board, so it is not ticked by default: a search for 베트남어
will usually come back empty while 개발자 / 프론트엔드 returns hundreds.
"""

from __future__ import annotations

from typing import Any

from app.collectors.base import JobCollector, NormalizedJob
from app.services.normalize_service import normalize_region, parse_deadline, parse_posted_at
from app.utils.text import clean_text

API_URL = "https://api.jumpit.co.kr/api/positions"
JOB_URL = "https://www.jumpit.co.kr/position/{id}"


class JumpitCollector(JobCollector):
    name = "jumpit"
    label = "점핏"
    site_url = "https://www.jumpit.co.kr"

    def search(self, keyword: str, limit: int = 50, **_options: Any) -> list[dict[str, Any]]:
        with self._client() as client:
            response = client.get(
                API_URL,
                params={"sort": "relation", "keyword": keyword, "page": 1},
                headers={"Accept": "application/json", "Referer": self.site_url},
            )
            response.raise_for_status()
            payload = response.json()

        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            return []
        positions = result.get("positions") or []
        return positions[:limit] if isinstance(positions, list) else []

    def normalize(self, raw_job: dict[str, Any]) -> NormalizedJob | None:
        job_id = raw_job.get("id")
        # search hits arrive wrapped in <span> highlight tags; clean_text strips them
        title = clean_text(raw_job.get("title"))
        if not title or job_id is None:
            return None

        locations = raw_job.get("locations") or raw_job.get("locationList") or []
        location = clean_text(", ".join(str(x) for x in locations)) if isinstance(locations, list) else None

        stacks = raw_job.get("techStacks") or []
        description = clean_text(
            ", ".join(str(s) for s in stacks) if isinstance(stacks, list) else None,
            max_length=300,
        )

        return NormalizedJob(
            source=self.name,
            source_job_id=str(job_id),
            title=title,
            company=clean_text(raw_job.get("companyName")) or "회사명 비공개",
            location=location,
            location_region=normalize_region(location),
            employment_type="정규직",  # Jumpit lists full-time developer roles
            experience=self._experience(raw_job),
            description=description,
            keywords=clean_text(raw_job.get("jobCategory")),
            url=JOB_URL.format(id=job_id),
            deadline=parse_deadline(raw_job.get("closedAt")),
        )

    @staticmethod
    def _experience(raw_job: dict[str, Any]) -> str | None:
        if raw_job.get("newcomer"):
            return "신입"
        min_career = raw_job.get("minCareer")
        if min_career is None:
            return None
        return "신입" if min_career == 0 else "경력"
