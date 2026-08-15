"""MockJobCollector - DEVELOPMENT DATA, clearly flagged as such.

Used in two ways:

* as its own source (``mock``) for local UI work;
* as a stand-in for a real source that is unavailable, when
  ``DEMO_MODE=true``. In that mode the rows carry the real source's name
  but keep ``is_mock=True``, and the UI paints them with a DEMO badge.

The ``url`` of a mock row points at the real site's public search page for the
keyword, so "원문 보기" always opens something real instead of a dead link.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from app.collectors.base import JobCollector, NormalizedJob
from app.collectors.mock_data import MOCK_JOBS
from app.services.normalize_service import (
    normalize_employment_type,
    normalize_experience,
    normalize_region,
    parse_salary,
)

# public search pages, used to give mock rows a link that actually resolves
SEARCH_PAGE = {
    "saramin": "https://www.saramin.co.kr/zf_user/search/recruit?searchword={q}",
    "jobkorea": "https://www.jobkorea.co.kr/Search/?stext={q}",
    "wanted": "https://www.wanted.co.kr/search?query={q}",
    "work24": "https://www.work24.go.kr/wk/a/b/1200/retriveDtlEmpSrchList.do?keyword={q}",
    "albamon": "https://www.albamon.com/jobs/search?keyword={q}",
    "alba": "https://www.alba.co.kr/search/Search.asp?strKeyword={q}",
    "indeed": "https://kr.indeed.com/jobs?q={q}",
    "mock": "https://www.saramin.co.kr/zf_user/search/recruit?searchword={q}",
}


class MockJobCollector(JobCollector):
    name = "mock"
    label = "샘플 데이터"
    site_url = ""

    def __init__(self, as_source: str | None = None, as_label: str | None = None) -> None:
        self.as_source = as_source or self.name
        self.as_label = as_label or self.label

    def is_available(self) -> bool:
        return True

    def search(self, keyword: str, limit: int = 50, **_options: Any) -> list[dict[str, Any]]:
        keyword = (keyword or "").strip()
        if not keyword:
            matches = list(MOCK_JOBS[:limit])
        else:
            needle = keyword.lower()
            matches = [
                job
                for job in MOCK_JOBS
                if needle in job["title"].lower()
                or needle in job["company"].lower()
                or needle in job["description"].lower()
                or any(needle in tag.lower() or tag.lower() in needle for tag in job["tags"])
            ][:limit]
            if not matches:
                matches = self._synthesize(keyword)
        # copy, never mutate the shared fixtures; normalize() needs the keyword
        # to build a real search-page link
        return [{**job, "_keyword": keyword} for job in matches]

    def _synthesize(self, keyword: str) -> list[dict[str, Any]]:
        """Keep the demo useful for keywords the fixture set does not cover."""
        templates = [
            ("{k} 담당자 채용", "서울 강남구", "연봉 3,400만원", "정규직", "경력무관"),
            ("{k} 경력직 모집", "경기 성남시", "연봉 4,100만원", "정규직", "경력"),
            ("{k} 신입사원 공개채용", "인천 남동구", "연봉 3,000만원", "정규직", "신입"),
            ("{k} 파트타임 모집", "부산 해운대구", "시급 12,500원", "아르바이트", "경력무관"),
            ("{k} 계약직 채용 공고", "대전 유성구", "월급 270만원", "계약직", "경력무관"),
            ("{k} 인턴 채용", "서울 마포구", "월급 220만원", "인턴", "신입"),
        ]
        companies = ["코리아파트너스", "대한산업", "글로벌솔루션", "한빛테크", "서울무역", "미래인력"]
        return [
            {
                "id": f"gen-{abs(hash(keyword)) % 100000}-{i}",
                "title": title.format(k=keyword),
                "company": companies[i % len(companies)],
                "location": location,
                "salary": salary,
                "employment_type": emp,
                "experience": exp,
                "days_ago": i,
                "description": f"'{keyword}' 관련 업무를 담당할 인재를 모집합니다. (샘플 데이터)",
                "tags": [keyword],
            }
            for i, (title, location, salary, emp, exp) in enumerate(templates)
        ]

    def normalize(self, raw_job: dict[str, Any]) -> NormalizedJob | None:
        keyword = raw_job.get("_keyword", "")
        template = SEARCH_PAGE.get(self.as_source, SEARCH_PAGE["mock"])
        url = template.format(q=quote(keyword or raw_job["title"]))

        salary_text, salary_value = parse_salary(raw_job.get("salary"))
        posted_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            days=int(raw_job.get("days_ago", 0))
        )

        return NormalizedJob(
            source=self.as_source,
            source_job_id=f"mock-{raw_job['id']}",
            title=raw_job["title"],
            company=raw_job["company"],
            location=raw_job.get("location"),
            location_region=normalize_region(raw_job.get("location")),
            salary=salary_text,
            salary_value=salary_value,
            employment_type=normalize_employment_type(raw_job.get("employment_type")),
            experience=normalize_experience(raw_job.get("experience")),
            description=raw_job.get("description"),
            url=url,
            posted_at=posted_at,
            is_mock=True,
        )
