"""Sources that exist in the UI but cannot be collected legitimately today.

They implement the full JobCollector interface and simply report why they are
unavailable, which is exactly the contract the search service expects: the source
shows up in /api/sources with a reason, it never crashes a search, and turning it
into a real collector later is a matter of filling in search() + normalize().

None of these are "blocked" in a way we should route around - that is the point.
"""

from __future__ import annotations

from typing import Any

from app.collectors.base import JobCollector, NormalizedJob


class _PlaceholderCollector(JobCollector):
    """Interface-complete collector that never returns rows."""

    def search(self, keyword: str, limit: int = 50, **_options: Any) -> list[dict[str, Any]]:
        return []

    def normalize(self, raw_job: dict[str, Any]) -> NormalizedJob | None:
        return None


class AlbamonCollector(_PlaceholderCollector):
    name = "albamon"
    label = "알바몬"
    site_url = "https://www.albamon.com"
    unavailable_reason = "Search results are rendered client-side and the listing API requires a session; no public API."


class AlbaCollector(_PlaceholderCollector):
    name = "alba"
    label = "알바천국"
    site_url = "https://www.alba.co.kr"
    unavailable_reason = "No public API; automated access to the search pages is restricted by the site's terms."


class IndeedCollector(_PlaceholderCollector):
    name = "indeed"
    label = "인디드 코리아"
    site_url = "https://kr.indeed.com"
    unavailable_reason = "Indeed retired its public Job Search API; scraping is blocked by bot protection and disallowed by its terms."


class CareerCollector(_PlaceholderCollector):
    name = "career"
    label = "커리어"
    site_url = "https://www.career.co.kr"
    unavailable_reason = "The search page answers 403 to non-browser requests; no public API."


class JobPlanetCollector(_PlaceholderCollector):
    name = "jobplanet"
    label = "잡플래닛"
    site_url = "https://www.jobplanet.co.kr"
    unavailable_reason = "Job search answers 403 without a signed-in session; no public API."


class KoworkCollector(_PlaceholderCollector):
    name = "kowork"
    label = "코워크"
    site_url = "https://kowork.kr"
    unavailable_reason = (
        "Listings load client-side after hydration; the HTML (even with an RSC request) "
        "carries no postings and no public API endpoint is exposed."
    )


class KWorkCollector(_PlaceholderCollector):
    name = "kwork"
    label = "K-Work"
    site_url = "https://k-work.or.kr"
    unavailable_reason = (
        "The 채용정보 list page returns only a page shell (the postings arrive by AJAX); "
        "the search form posts srchText but the response carries no listings, and no public "
        "job-list endpoint is exposed."
    )


class BuddiesKoreaCollector(_PlaceholderCollector):
    name = "buddieskorea"
    label = "버디즈코리아"
    site_url = "https://www.buddieskorea.com"
    unavailable_reason = (
        "Listings are fetched client-side from the site's own Supabase backend; the served "
        "HTML says '채용공고를 불러오는 중입니다... 총 0건' and every /jobs-style path returns 404."
    )


class RocketPunchCollector(_PlaceholderCollector):
    name = "rocketpunch"
    label = "로켓펀치"
    site_url = "https://www.rocketpunch.com"
    unavailable_reason = "Listings are rendered client-side; the HTML response contains no job entries."
