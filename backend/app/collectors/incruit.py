"""인크루트 (Incruit) - public search page.

A plain GET on the same public search URL a browser opens. The page is served as
EUC-KR; httpx honours the declared charset, so response.text is already decoded.

Cards are ``ul.c_row`` blocks, each holding one posting. As with JobKorea we
anchor on the structural thing - links to ``/jobdb_info/jobpost.asp?job={id}`` -
and only use class names as a fast path.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from bs4 import BeautifulSoup, Tag

from app.collectors.base import JobCollector, NormalizedJob
from app.services.normalize_service import (
    KST,
    REGIONS,
    find_salary_text,
    normalize_employment_type,
    normalize_experience,
    normalize_region,
    parse_posted_at,
    parse_salary,
)
from app.utils.text import absolute_url, clean_text

SEARCH_URL = "https://job.incruit.com/jobdb_list/searchjob.asp"
BASE = "https://job.incruit.com"

JOB_LINK = re.compile(r"jobdb_info/jobpost\.asp\?job=(\d+)")
COMPANY_LINK = re.compile(r"company|corp", re.IGNORECASE)
LOCATION = re.compile(rf"(?:{'|'.join(REGIONS)})(?:\s+\S+?[시군구])?")
# "(1일전 등록)", "(오늘 등록)"
POSTED = re.compile(r"\(([^)]*?(?:등록|전))\)")
# "~09.06 (일)" - the application deadline, month/day only
DEADLINE = re.compile(r"~\s*(\d{1,2})[.\-/](\d{1,2})")


class IncruitCollector(JobCollector):
    name = "incruit"
    label = "인크루트"
    site_url = BASE

    def search(self, keyword: str, limit: int = 50, **_options: Any) -> list[dict[str, Any]]:
        with self._client() as client:
            response = client.get(SEARCH_URL, params={"kw": keyword})
            response.raise_for_status()
            html = response.text

        soup = BeautifulSoup(html, "html.parser")
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for link in soup.find_all("a", href=True):
            match = JOB_LINK.search(link["href"])
            if not match:
                continue
            job_id = match.group(1)
            title = clean_text(link.get_text(" ", strip=True))
            if not title or len(title) < 5 or job_id in seen:
                continue
            seen.add(job_id)

            card = self._card_for(link)
            rows.append(
                {
                    "job_id": job_id,
                    "href": link["href"],
                    "title": title,
                    "company": self._company_of(card, title),
                    "detail": self._detail_of(card, title),
                }
            )
            if len(rows) >= limit:
                break
        return rows

    @staticmethod
    def _card_for(link: Tag) -> Tag:
        """The ``ul.c_row`` ancestor, or the nearest block that holds the whole row."""
        node: Tag | None = link
        while isinstance(node, Tag) and node.name != "body":
            classes = node.get("class") or []
            if node.name == "ul" and "c_row" in classes:
                return node
            node = node.parent
        return link.parent if isinstance(link.parent, Tag) else link

    @staticmethod
    def _company_of(card: Tag, title: str) -> str | None:
        for anchor in card.find_all("a", href=True):
            if COMPANY_LINK.search(anchor["href"]) and not JOB_LINK.search(anchor["href"]):
                if name := clean_text(anchor.get_text(" ", strip=True)):
                    return name
        candidates = [
            text
            for anchor in card.find_all("a", href=True)
            if not JOB_LINK.search(anchor["href"])
            and (text := clean_text(anchor.get_text(" ", strip=True)))
            and text != title
            and 1 < len(text) <= 40
            and text not in {"관심기업", "스크랩", "바로지원", "홈페이지 지원"}
        ]
        return candidates[0] if candidates else None

    @staticmethod
    def _detail_of(card: Tag, title: str) -> str:
        text = clean_text(card.get_text(" ", strip=True)) or ""
        for noise in (title, "관심기업", "스크랩", "바로지원", "홈페이지 지원"):
            text = text.replace(noise, " ")
        return " ".join(text.split())

    @staticmethod
    def _deadline(detail: str, today: date | None = None) -> datetime | None:
        """Read "~09.06" off the card.

        Only month/day is shown, so December postings closing in January would
        land in the past - roll those into next year.
        """
        match = DEADLINE.search(detail)
        if not match:
            return None
        today = today or datetime.now(KST).date()
        month, day = int(match.group(1)), int(match.group(2))
        for year in (today.year, today.year + 1):
            try:
                candidate = datetime(year, month, day, 23, 59)
            except ValueError:
                return None
            if candidate.date() >= today:
                return candidate
        return None

    def normalize(self, raw_job: dict[str, Any]) -> NormalizedJob | None:
        title = clean_text(raw_job.get("title"))
        url = absolute_url(raw_job.get("href"), BASE)
        if not title or not url:
            return None

        detail = raw_job.get("detail") or ""
        company = clean_text(raw_job.get("company"))
        if company:
            detail = detail.replace(company, " ").strip()

        location_match = LOCATION.search(detail)
        location = clean_text(location_match.group(0)) if location_match else None

        salary_text, salary_value = parse_salary(find_salary_text(detail))

        # "(1일전 등록)" / "(오늘 등록)" sits at the tail of the row
        posted_match = POSTED.search(detail)
        posted_at = parse_posted_at(posted_match.group(1)) if posted_match else None

        education = None
        if edu := re.search(r"(고졸|초대졸|대졸|석사|박사|학력무관)[↑이상]*", detail):
            education = edu.group(0)

        deadline = self._deadline(detail)

        return NormalizedJob(
            source=self.name,
            source_job_id=raw_job.get("job_id"),
            title=title,
            company=company or "회사명 비공개",
            location=location,
            location_region=normalize_region(location or detail),
            salary=salary_text,
            salary_value=salary_value,
            employment_type=normalize_employment_type(f"{title} {detail}"),
            experience=normalize_experience(detail),
            education=education,
            description=clean_text(detail, 300),
            url=url,
            posted_at=posted_at,
            deadline=deadline,
        )
