"""Small text helpers shared by the collectors."""

from __future__ import annotations

import html
import re

_WHITESPACE = re.compile(r"\s+")
_TAGS = re.compile(r"<[^>]+>")


def clean_text(value: object, max_length: int | None = None) -> str | None:
    """Unescape entities, drop tags, collapse whitespace. Returns None when empty."""
    if value is None:
        return None
    text = str(value)
    if not text.strip():
        return None
    text = _TAGS.sub(" ", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = _WHITESPACE.sub(" ", text).strip()
    if not text:
        return None
    if max_length and len(text) > max_length:
        text = text[:max_length].rstrip() + "..."
    return text


def absolute_url(href: str | None, base: str) -> str | None:
    """Turn a site-relative href into an absolute URL."""
    if not href:
        return None
    href = href.strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if not href.startswith("/"):
        href = "/" + href
    return base.rstrip("/") + href
