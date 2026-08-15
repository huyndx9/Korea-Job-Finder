"""Collector driven by configuration instead of code.

Lets a user add a job site from the UI: give it a search URL containing
``{keyword}`` plus a few CSS selectors (HTML sites) or dotted paths (JSON APIs),
and it behaves like any built-in collector - same interface, same normalization,
same dedup, same error reporting.

Two rules it inherits from every other collector:
  * the URL is fetched with one plain, well-identified GET - nothing here logs
    in, solves a captcha, or works around a block;
  * a failure is reported, never papered over.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlsplit

import httpx
from bs4 import BeautifulSoup, Tag

from app.collectors.base import CollectorError, JobCollector, NormalizedJob, SourceStatus
from app.models.custom_source import CustomSource
from app.services.normalize_service import (
    find_salary_text,
    normalize_employment_type,
    normalize_experience,
    normalize_region,
    parse_posted_at,
    parse_salary,
)
from app.utils.text import absolute_url, clean_text
from app.utils.url_guard import KEYWORD_PLACEHOLDER, UnsafeUrlError, validate_search_url

HTML = "html"
JSON = "json"


def dig(data: Any, path: str | None) -> Any:
    """Follow a dotted path such as ``result.positions`` or ``a.0.b``."""
    if not path:
        return None
    current = data
    for part in path.split("."):
        if current is None:
            return None
        if isinstance(current, list):
            if not part.isdigit():
                return None
            index = int(part)
            current = current[index] if -len(current) <= index < len(current) else None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


class CustomCollector(JobCollector):
    """One user-configured site."""

    def __init__(self, config: CustomSource) -> None:
        self.config = config
        self.name = config.name
        self.label = config.label
        self.site_url = config.site_url or self._origin(config.search_url)
        self.is_custom = True

    @staticmethod
    def _origin(url: str) -> str:
        parts = urlsplit(url.replace(KEYWORD_PLACEHOLDER, "x"))
        return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ""

    @property
    def unavailable_reason(self) -> str | None:  # type: ignore[override]
        if not self.config.enabled:
            return "disabled"
        return None

    def unavailable_status(self) -> SourceStatus:
        return SourceStatus.UNAVAILABLE

    # ------------------------------------------------------------------ fetch

    def build_url(self, keyword: str) -> str:
        return self.config.search_url.replace(KEYWORD_PLACEHOLDER, quote(keyword))

    def search(self, keyword: str, limit: int = 50, **_options: Any) -> list[dict[str, Any]]:
        try:
            validate_search_url(self.config.search_url)
        except UnsafeUrlError as exc:
            raise CollectorError(SourceStatus.INVALID_REQUEST, str(exc)) from exc

        url = self.build_url(keyword)
        headers = {"Accept": "application/json"} if self.config.kind == JSON else {}
        try:
            with self._client() as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                body = response.json() if self.config.kind == JSON else response.text
        except httpx.HTTPStatusError as exc:
            raise CollectorError(
                SourceStatus.API_ERROR, f"HTTP {exc.response.status_code} from {self.label}"
            ) from exc
        except httpx.HTTPError as exc:
            raise CollectorError(SourceStatus.ERROR, f"request failed: {exc}") from exc
        except ValueError as exc:  # JSON mode, non-JSON body
            raise CollectorError(SourceStatus.API_ERROR, "response was not valid JSON") from exc

        rows = self._extract_json(body, limit) if self.config.kind == JSON else self._extract_html(body, limit)
        return rows

    # ---------------------------------------------------------------- extract

    def _extract_json(self, payload: Any, limit: int) -> list[dict[str, Any]]:
        items = dig(payload, self.config.item_selector)
        if items is None and isinstance(payload, list):
            items = payload
        if not isinstance(items, list):
            raise CollectorError(
                SourceStatus.INVALID_REQUEST,
                f"'{self.config.item_selector}' did not point at a list in the response",
            )
        return [item for item in items[:limit] if isinstance(item, (dict, list))]

    def _extract_html(self, html: str, limit: int) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        try:
            cards = soup.select(self.config.item_selector)
        except Exception as exc:  # invalid CSS selector
            raise CollectorError(
                SourceStatus.INVALID_REQUEST, f"invalid item selector: {exc}"
            ) from exc
        return [{"_card": card} for card in cards[:limit]]

    # -------------------------------------------------------------- normalize

    def normalize(self, raw_job: dict[str, Any] | list[Any]) -> NormalizedJob | None:
        if self.config.kind == JSON:
            get = lambda selector: self._json_value(raw_job, selector)  # noqa: E731
            link_value = dig(raw_job, self.config.link_selector) if self.config.link_selector else None
        else:
            card = raw_job["_card"]
            get = lambda selector: self._html_text(card, selector)  # noqa: E731
            link_value = self._html_link(card)

        title = clean_text(get(self.config.title_selector))
        url = self._build_link(link_value)
        if not title or not url:
            return None

        location = clean_text(get(self.config.location_selector))
        description = clean_text(get(self.config.description_selector), 400)
        salary_raw = clean_text(get(self.config.salary_selector))
        salary_text, salary_value = parse_salary(salary_raw or find_salary_text(description))

        blob = " ".join(filter(None, [title, description, location]))

        return NormalizedJob(
            source=self.name,
            source_job_id=self._source_job_id(link_value, url),
            title=title,
            company=clean_text(get(self.config.company_selector)) or "회사명 비공개",
            location=location,
            location_region=normalize_region(location or blob),
            salary=salary_text,
            salary_value=salary_value,
            employment_type=normalize_employment_type(blob),
            experience=normalize_experience(blob),
            description=description,
            url=url,
            posted_at=parse_posted_at(clean_text(get(self.config.date_selector))),
        )

    # ------------------------------------------------------------- value bits

    @staticmethod
    def _json_value(row: Any, path: str | None) -> str | None:
        value = dig(row, path)
        if isinstance(value, (list, tuple)):
            return ", ".join(str(v) for v in value if v is not None) or None
        return str(value) if value is not None else None

    @staticmethod
    def _html_text(card: Tag, selector: str | None) -> str | None:
        if not selector:
            return None
        try:
            node = card.select_one(selector)
        except Exception:
            return None
        return node.get_text(" ", strip=True) if node else None

    def _html_link(self, card: Tag) -> str | None:
        selector = self.config.link_selector or "a"
        try:
            node = card.select_one(selector)
        except Exception:
            node = None
        if node is None:
            node = card if card.name == "a" else card.select_one("a")
        if node is None:
            return None
        return node.get("href") or None

    def _build_link(self, value: str | None) -> str | None:
        if not value:
            return None
        value = str(value).strip()
        if self.config.link_template:
            return self.config.link_template.replace("{value}", value)
        return absolute_url(value, self.site_url or "")

    @staticmethod
    def _source_job_id(link_value: str | None, url: str) -> str | None:
        """Pull a stable id out of the link so re-searches dedupe cleanly.

        Handles both path ids (``/jobs/12345``) and query ids
        (``?job=12345&src=g``); falls back to the content fingerprint when the
        link carries no number at all.
        """
        candidate = str(link_value or url)
        for separator in ("?", "&", "=", "#"):
            candidate = candidate.replace(separator, "/")
        digits = [part for part in candidate.split("/") if part.isdigit() and len(part) >= 4]
        return digits[-1] if digits else None


def build_custom_collectors(sources: list[CustomSource]) -> dict[str, CustomCollector]:
    return {source.name: CustomCollector(source) for source in sources}
