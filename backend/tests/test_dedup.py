"""Deduplication rules."""

from __future__ import annotations

from app.collectors.base import NormalizedJob
from app.services.dedup_service import content_key, deduplicate, make_fingerprint


def job(**overrides) -> NormalizedJob:
    defaults = dict(
        source="saramin",
        title="베트남어 통역 담당자",
        company="ABC 주식회사",
        url="https://example.com/1",
        source_job_id="1001",
        location="서울 강남구",
        location_region="서울",
    )
    defaults.update(overrides)
    return NormalizedJob(**defaults)


def test_same_source_and_source_job_id_is_one_job():
    jobs = [job(url="https://example.com/a"), job(url="https://example.com/b")]
    assert len(deduplicate(jobs)) == 1


def test_different_source_job_id_from_same_source_are_kept():
    jobs = [job(source_job_id="1"), job(source_job_id="2", title="다른 공고", company="다른회사")]
    assert len(deduplicate(jobs)) == 2


def test_same_company_title_location_dedupes_across_sources():
    """The same opening cross-posted to two sites, with different ids."""
    jobs = [
        job(source="saramin", source_job_id="1"),
        job(source="jobkorea", source_job_id="99", url="https://jobkorea.co.kr/9"),
    ]
    assert len(deduplicate(jobs)) == 1


def test_dedup_ignores_cosmetic_company_differences():
    a = job(company="ABC 주식회사", source_job_id=None)
    b = job(company="(주)ABC", source_job_id=None, url="https://example.com/2")
    assert content_key(a) == content_key(b)
    assert len(deduplicate([a, b])) == 1


def test_missing_source_job_id_falls_back_to_content_fingerprint():
    without_id = job(source_job_id=None)
    fingerprint = make_fingerprint(without_id)
    assert fingerprint == make_fingerprint(job(source_job_id=None, url="https://other.example/x"))
    assert fingerprint != make_fingerprint(job(source_job_id="1001"))


def test_distinct_jobs_survive():
    jobs = [
        job(source_job_id="1", title="베트남어 통역"),
        job(source_job_id="2", title="베트남어 영업", company="다른회사"),
        job(source_job_id="3", title="외국인 생산직", company="세번째회사"),
    ]
    assert len(deduplicate(jobs)) == 3


def test_fingerprint_is_stable_and_assigned():
    jobs = deduplicate([job()])
    assert jobs[0].fingerprint
    assert jobs[0].fingerprint == make_fingerprint(job())
