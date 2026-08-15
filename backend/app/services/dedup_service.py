"""Duplicate detection.

Two levels, exactly as specified:

1. ``source + source_job_id`` - the same posting seen twice from one site.
2. ``company + title + location`` - the same posting cross-listed on several
   sites, or re-posted by the company without a stable id.

Both are reduced to a single ``fingerprint`` string stored on the row, so the
DB's UNIQUE index does the deduplication for us on repeat searches too.
"""

from __future__ import annotations

import hashlib
import re

from app.collectors.base import NormalizedJob

_NOISE = re.compile(r"[\s\-_,./()\[\]{}·•ㆍ|!?~*\"']+")
_CORP_SUFFIX = re.compile(r"주식회사|㈜|\(주\)|\(유\)|유한회사|co\.,?\s*ltd\.?|inc\.?|corp\.?", re.IGNORECASE)


def _norm(value: str | None) -> str:
    """Aggressively normalize a string so cosmetic differences stop mattering."""
    if not value:
        return ""
    text = str(value).lower()
    text = _CORP_SUFFIX.sub("", text)
    text = _NOISE.sub("", text)
    return text.strip()


def content_key(job: NormalizedJob) -> str:
    """company + title + location, normalized. Source-agnostic on purpose."""
    return f"{_norm(job.company)}|{_norm(job.title)}|{_norm(job.location_region or job.location)}"


def make_fingerprint(job: NormalizedJob) -> str:
    """Stable dedup key for one posting."""
    if job.source_job_id:
        basis = f"id:{job.source}:{str(job.source_job_id).strip()}"
    else:
        basis = f"content:{content_key(job)}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


def deduplicate(jobs: list[NormalizedJob]) -> list[NormalizedJob]:
    """Drop repeats from one search, keeping the first occurrence of each posting.

    A job is a duplicate when its fingerprint repeats, OR when an earlier job
    already had the same company/title/location - that second check is what
    catches the same opening cross-posted to Saramin and JobKorea under
    different ids.
    """
    seen_fingerprints: set[str] = set()
    seen_content: set[str] = set()
    unique: list[NormalizedJob] = []

    for job in jobs:
        fingerprint = job.fingerprint or make_fingerprint(job)
        job.fingerprint = fingerprint
        key = content_key(job)

        if fingerprint in seen_fingerprints:
            continue
        # only trust the content key when we actually have a company and a title
        if _norm(job.company) and _norm(job.title) and key in seen_content:
            continue

        seen_fingerprints.add(fingerprint)
        seen_content.add(key)
        unique.append(job)

    return unique
