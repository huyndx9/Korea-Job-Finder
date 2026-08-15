"""잡플로이 (JOBPLOY) - 외국인 채용 전문 사이트, public search page.

https://www.jobploy.kr/ko/recruit?search={keyword}

A job board aimed squarely at foreigners working in Korea, which makes it a
strong fit for 베트남어 / 외국인 style searches. The listing is server-rendered,
so one plain GET is enough - no login, no captcha, no anti-bot workaround.

One site quirk we have to compensate for: when a keyword has no matches, the
site does NOT return an empty list - it silently falls back to its default,
mostly-sponsored feed. Measured on the live site:

    검색어 '용접'    -> 36 cards, 32 really contain 용접
    검색어 '베트남어' -> 50 cards,  0 contain 베트남어  (all default/ad rows)

Passing that straight through would inject 50 irrelevant postings into the
results, so the collector keeps only rows that actually mention the keyword.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from bs4 import BeautifulSoup, Tag

from app.collectors.base import JobCollector, NormalizedJob
from app.services.normalize_service import (
    KST,
    normalize_employment_type,
    normalize_experience,
    normalize_region,
    parse_salary,
)
from app.utils.text import absolute_url, clean_text

SEARCH_URL = "https://www.jobploy.kr/ko/recruit"
BASE = "https://www.jobploy.kr"

# "마감 D-143"
DEADLINE = re.compile(r"D-\s*(\d+)")
SALARY_HINT = re.compile(r"(연봉|월급|시급|일급|주급|급여)")


class JobployCollector(JobCollector):
    name = "jobploy"
    label = "잡플로이"
    site_url = BASE

    def search(self, keyword: str, limit: int = 50, **_options: Any) -> list[dict[str, Any]]:
        with self._client() as client:
            # NOTE: the parameter is `search`. `query` is accepted but ignored -
            # it returns the unfiltered default feed.
            response = client.get(SEARCH_URL, params={"search": keyword})
            response.raise_for_status()
            html = response.text

        soup = BeautifulSoup(html, "html.parser")
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for card in soup.select("div.recruit-list div.item"):
            link = card.select_one("a[href]")
            if link is None:
                continue
            href = link["href"]
            if "/recruit/" not in href:
                continue

            text = clean_text(card.get_text(" ", strip=True)) or ""
            # the site pads thin results with its default feed - drop anything
            # that does not actually mention what the user searched for
            if keyword and keyword.lower() not in text.lower():
                continue

            slug = href.rstrip("/").split("/")[-1].split("?")[0]
            if slug in seen:
                continue
            seen.add(slug)

            rows.append(
                {
                    "slug": slug,
                    "href": href,
                    "title": self._text(card, "div.title"),
                    "company": self._text(card, "span.text-info"),
                    "tags": [
                        clean_text(tag.get_text(" ", strip=True))
                        for tag in card.select("span.tag")
                    ],
                }
            )
            if len(rows) >= limit:
                break
        return rows

    @staticmethod
    def _text(card: Tag, selector: str) -> str | None:
        node = card.select_one(selector)
        return clean_text(node.get_text(" ", strip=True)) if node else None

    def normalize(self, raw_job: dict[str, Any]) -> NormalizedJob | None:
        title = clean_text(raw_job.get("title"))
        url = absolute_url(raw_job.get("href"), BASE)
        if not title or not url:
            return None

        tags = [tag for tag in (raw_job.get("tags") or []) if tag]

        # Pass the WHOLE tag ("월급 : 2,500,000 원"): the period prefix is what
        # tells parse_salary to annualise. Extracting just the money expression
        # first would turn a 2.5M-per-month job into 250만원 a year.
        salary_tag = next((t for t in tags if SALARY_HINT.search(t)), None)
        salary_text, salary_value = parse_salary(salary_tag)

        location = next((t for t in tags if normalize_region(t)), None)
        deadline = self._deadline(" ".join(tags))

        # whatever is left over describes the work itself
        leftovers = [t for t in tags if t not in {salary_tag, location} and not DEADLINE.search(t)]
        description = clean_text(" · ".join(leftovers), 300)

        blob = f"{title} {description or ''}"

        return NormalizedJob(
            source=self.name,
            source_job_id=raw_job.get("slug"),
            title=title,
            company=clean_text(raw_job.get("company")) or "회사명 비공개",
            location=location,
            location_region=normalize_region(location or blob),
            salary=salary_text,
            salary_value=salary_value,
            employment_type=normalize_employment_type(blob),
            experience=normalize_experience(blob),
            description=description,
            url=url,
            # the listing shows a countdown, never a posting date
            deadline=deadline,
        )

    @staticmethod
    def _deadline(text: str, now: datetime | None = None) -> datetime | None:
        """"마감 D-143" -> a real date, counted from today."""
        match = DEADLINE.search(text or "")
        if not match:
            return None
        days = int(match.group(1))
        if days > 365 * 5:  # same 상시채용 guard the other sources use
            return None
        today = (now or datetime.now(KST)).replace(tzinfo=None)
        return (today + timedelta(days=days)).replace(hour=23, minute=59, second=0, microsecond=0)
