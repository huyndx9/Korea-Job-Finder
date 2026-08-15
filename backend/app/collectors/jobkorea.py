"""잡코리아 (JobKorea) - public search page, parsed with BeautifulSoup.

A plain GET on the same public search URL a browser opens, with a normal
User-Agent. No login, no captcha handling, no anti-bot evasion: if JobKorea
answers with a block page we parse zero rows and report the source as failed.

The site's markup is built from utility classes (``flex``, ``w-full``, ...) with
no stable semantic hooks, so we do not pin selectors to them. Instead we anchor
on the one thing that is structural: links to ``/Recruit/GI_Read/{id}``. A card
is the largest ancestor of such a link that still contains exactly one job id.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import quote

from bs4 import BeautifulSoup, Tag

from app.collectors.base import JobCollector, NormalizedJob
from app.services.normalize_service import (
    REGIONS,
    find_salary_text,
    normalize_employment_type,
    normalize_experience,
    normalize_region,
    parse_deadline,
    parse_posted_at,
    parse_salary,
)
from app.utils.text import absolute_url, clean_text

SEARCH_URL = "https://www.jobkorea.co.kr/Search/?stext={q}&tabType=recruit&Page_No=1"
BASE = "https://www.jobkorea.co.kr"

JOB_ID = re.compile(r"/Recruit/GI_Read/(\d+)")
COMPANY_LINK = re.compile(r"Co_Read|/company/|Corp_Read", re.IGNORECASE)
# the page also ships its data as JSON inside a JS string literal
CONTENT_ARRAY = re.compile(r'"content"\s*:\s*\[')

logger = logging.getLogger(__name__)
# "서울 서초구", "경기 안양시", "충남 천안시" ...
LOCATION = re.compile(rf"(?:{'|'.join(REGIONS)})(?:\s+\S+?[시군구])?")


class JobKoreaCollector(JobCollector):
    name = "jobkorea"
    label = "잡코리아"
    site_url = BASE

    def search(self, keyword: str, limit: int = 50, **_options: Any) -> list[dict[str, Any]]:
        with self._client() as client:
            response = client.get(SEARCH_URL.format(q=quote(keyword)))
            response.raise_for_status()
            html = response.text

        soup = BeautifulSoup(html, "html.parser")
        # the cards carry no date; the embedded payload does, keyed by the same id
        embedded = self._embedded_records(html)

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for link in soup.find_all("a", href=True):
            match = JOB_ID.search(link["href"])
            if not match:
                continue
            job_id = match.group(1)
            title = clean_text(link.get_text(" ", strip=True))
            # several links point at one job (thumbnail, title, company);
            # the title link is the one carrying real text
            if not title or len(title) < 5 or job_id in seen:
                continue
            seen.add(job_id)

            card = self._card_for(link, job_id)
            record = embedded.get(job_id, {})
            keywords = record.get("_internal_keywordList")

            rows.append(
                {
                    "job_id": job_id,
                    "href": link["href"],
                    "title": title,
                    "company": self._company_of(card, title),
                    "detail": self._detail_of(card, title),
                    # from the embedded payload, when present
                    "date": record.get("createdAt"),
                    "deadline": (record.get("applicationPeriod") or {}).get("end"),
                    "keywords": ",".join(keywords) if isinstance(keywords, list) else None,
                }
            )
            if len(rows) >= limit:
                break
        return rows

    @staticmethod
    def _embedded_records(html: str) -> dict[str, dict[str, Any]]:
        """Job records the page ships as JSON, keyed by job id.

        The search cards show no posting date, but the page embeds the same
        results as JSON (inside a JS string, so quotes arrive escaped). Reading
        it costs nothing extra - it is the response we already fetched - and
        avoids one detail-page request per row just to learn a date.

        Returns {} if the payload is missing or unreadable; the caller then
        simply has no dates, exactly as before.
        """
        unescaped = html.replace('\\"', '"')
        decoder = json.JSONDecoder()

        for match in CONTENT_ARRAY.finditer(unescaped):
            try:
                array, _ = decoder.raw_decode(unescaped[match.end() - 1 :])
            except ValueError:
                continue
            if not isinstance(array, list) or not array:
                continue
            first = array[0]
            # several unrelated "content" arrays exist (promo banners, regions);
            # the job one is identifiable by its fields
            if isinstance(first, dict) and "createdAt" in first and "id" in first:
                return {str(item["id"]): item for item in array if isinstance(item, dict) and item.get("id")}

        logger.debug("jobkorea: no embedded job payload found; dates unavailable")
        return {}

    @staticmethod
    def _card_for(link: Tag, job_id: str) -> Tag:
        """Largest ancestor that still describes only this one job."""
        card: Tag = link
        node = link.parent
        while isinstance(node, Tag) and node.name != "body":
            ids = {m for m in JOB_ID.findall(str(node.get("href", "")) or "")}
            ids |= {m.group(1) for a in node.find_all("a", href=True) if (m := JOB_ID.search(a["href"]))}
            if ids and ids != {job_id}:
                break
            card = node
            node = node.parent
        return card

    @staticmethod
    def _company_of(card: Tag, title: str) -> str | None:
        for anchor in card.find_all("a", href=True):
            if COMPANY_LINK.search(anchor["href"]):
                if name := clean_text(anchor.get_text(" ", strip=True)):
                    return name
        # fall back to the shortest non-title link text in the card
        candidates = [
            text
            for anchor in card.find_all("a", href=True)
            if (text := clean_text(anchor.get_text(" ", strip=True)))
            and text != title
            and 1 < len(text) <= 40
        ]
        return min(candidates, key=len) if candidates else None

    @staticmethod
    def _detail_of(card: Tag, title: str) -> str:
        """Everything on the card except the title - location / type / experience chips."""
        text = clean_text(card.get_text(" ", strip=True)) or ""
        return text.replace(title, " ").replace("스크랩", " ").strip()

    @staticmethod
    def _summary(detail: str, location: str | None) -> str | None:
        """Trim the chip strip down to the part that reads like a description.

        The tail after "•" is a benefits list (4대보험, 퇴직금, ...) and the
        location is already its own field - neither belongs in the summary.
        """
        text = detail.split("•")[0]
        if location:
            text = text.replace(location, " ")
        return clean_text(text, 300)

    def normalize(self, raw_job: dict[str, Any]) -> NormalizedJob | None:
        title = clean_text(raw_job.get("title"))
        url = absolute_url(raw_job.get("href"), BASE)
        if not title or not url:
            return None

        detail = raw_job.get("detail") or ""
        company = clean_text(raw_job.get("company"))
        # the company name sits at the head of the chip strip - drop it before
        # reading location/type/experience out of the rest
        if company:
            detail = detail.replace(company, " ").strip()

        location_match = LOCATION.search(detail)
        location = clean_text(location_match.group(0)) if location_match else None

        salary_text, salary_value = parse_salary(find_salary_text(detail))
        # the listing rarely shows 고용형태 as a chip, but the title usually says it
        # ("...아르바이트 모집", "[프리랜서/재택]...")
        type_blob = f"{title} {detail}"

        return NormalizedJob(
            source=self.name,
            source_job_id=raw_job.get("job_id"),
            title=title,
            company=company or "회사명 비공개",
            location=location,
            location_region=normalize_region(location or detail),
            salary=salary_text,
            salary_value=salary_value,
            employment_type=normalize_employment_type(type_blob),
            experience=normalize_experience(detail),
            description=self._summary(detail, location),
            # date/deadline/keywords come from the payload embedded in the same page
            posted_at=parse_posted_at(raw_job.get("date")),
            deadline=parse_deadline(raw_job.get("deadline")),
            keywords=clean_text(raw_job.get("keywords")),
            url=url,
        )
