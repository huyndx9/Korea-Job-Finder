"""One broken source must never break a search."""

from __future__ import annotations

import time

import pytest

from app.collectors.base import JobCollector, NormalizedJob


class ExplodingCollector(JobCollector):
    name = "wanted"
    label = "원티드"
    site_url = "https://www.wanted.co.kr"

    def search(self, keyword: str, limit: int = 50):
        raise ConnectionError("connection reset by peer")

    def normalize(self, raw_job):  # pragma: no cover - never reached
        return None


class HangingCollector(JobCollector):
    name = "jobkorea"
    label = "잡코리아"
    site_url = "https://www.jobkorea.co.kr"

    def search(self, keyword: str, limit: int = 50):
        time.sleep(3)
        return []

    def normalize(self, raw_job):  # pragma: no cover - never reached
        return None


class WorkingCollector(JobCollector):
    name = "saramin"
    label = "사람인"
    site_url = "https://www.saramin.co.kr"

    def search(self, keyword: str, limit: int = 50):
        return [{"title": f"{keyword} 담당자", "company": "정상회사"}]

    def normalize(self, raw_job):
        return NormalizedJob(
            source=self.name,
            source_job_id="ok-1",
            title=raw_job["title"],
            company=raw_job["company"],
            url="https://example.com/ok-1",
        )


class BadRowCollector(WorkingCollector):
    name = "work24"
    label = "워크24"

    def search(self, keyword: str, limit: int = 50):
        return [{"title": "good", "company": "c"}, {"broken": True}, {"title": "good2", "company": "c2"}]

    def normalize(self, raw_job):
        if "title" not in raw_job:
            raise KeyError("title")  # one unreadable row
        return NormalizedJob(
            source=self.name,
            source_job_id=raw_job["title"],
            title=raw_job["title"],
            company=raw_job["company"],
            url=f"https://example.com/{raw_job['title']}",
        )


@pytest.fixture
def no_demo_mode(monkeypatch):
    """Demo mode is off by default; make that explicit for these tests."""
    monkeypatch.setattr("app.services.search_service.settings.demo_mode", False)


def _install(monkeypatch, collectors: dict) -> None:
    monkeypatch.setattr("app.services.search_service.build_collectors", lambda *_a, **_k: collectors)


def test_a_crashing_collector_does_not_fail_the_request(client, monkeypatch, no_demo_mode):
    _install(monkeypatch, {"saramin": WorkingCollector(), "wanted": ExplodingCollector()})

    response = client.post("/api/search", json={"keywords": ["베트남어"], "sources": ["saramin", "wanted"]})
    assert response.status_code == 200
    body = response.json()

    # the healthy source still delivered
    assert len(body["jobs"]) == 1
    assert body["jobs"][0]["source"] == "saramin"

    by_source = {s["source"]: s for s in body["sources"]}
    assert by_source["saramin"]["status"] == "connected"
    assert by_source["wanted"]["status"] == "error"
    assert by_source["wanted"]["ok"] is False
    assert "ConnectionError" in by_source["wanted"]["error"]


def test_a_hanging_collector_times_out_without_blocking_the_others(client, monkeypatch, no_demo_mode):
    monkeypatch.setattr("app.services.search_service.settings.collector_timeout", 0.2)
    _install(monkeypatch, {"saramin": WorkingCollector(), "jobkorea": HangingCollector()})

    body = client.post(
        "/api/search", json={"keywords": ["베트남어"], "sources": ["saramin", "jobkorea"]}
    ).json()

    by_source = {s["source"]: s for s in body["sources"]}
    assert by_source["jobkorea"]["status"] == "timeout"
    assert "timed out" in by_source["jobkorea"]["error"]
    assert by_source["saramin"]["status"] == "connected"
    assert len(body["jobs"]) == 1


def test_an_unreadable_row_does_not_lose_the_rest_of_the_page(client, monkeypatch, no_demo_mode):
    _install(monkeypatch, {"work24": BadRowCollector()})
    body = client.post("/api/search", json={"keywords": ["x"], "sources": ["work24"]}).json()

    assert body["sources"][0]["status"] == "connected"
    assert body["sources"][0]["count"] == 2  # the broken row was skipped


def test_unconfigured_source_is_reported_not_crashed(client, no_demo_mode):
    """saramin/work24 have no API key in the test environment."""
    body = client.post("/api/search", json={"keywords": ["베트남어"], "sources": ["saramin"]}).json()

    status = body["sources"][0]
    assert status["status"] == "not_configured"
    assert "SARAMIN_API_KEY" in status["error"]
    assert body["jobs"] == []


def test_demo_mode_stands_in_for_a_dead_source_and_flags_the_data(client, monkeypatch):
    """Only with DEMO_MODE=true is a dead source stood in for - and labelled."""
    monkeypatch.setattr("app.services.search_service.settings.demo_mode", True)
    _install(monkeypatch, {"wanted": ExplodingCollector()})

    body = client.post("/api/search", json={"keywords": ["베트남어"], "sources": ["wanted"]}).json()

    status = body["sources"][0]
    assert status["status"] == "demo"
    assert status["is_mock"] is True
    assert status["error"]  # the real failure is still reported
    assert body["jobs"]
    assert all(job["is_mock"] is True for job in body["jobs"])
    assert all(job["source"] == "wanted" for job in body["jobs"])


def test_two_searches_racing_on_the_same_posting_do_not_500(client, monkeypatch, no_demo_mode):
    """The loser of a concurrent insert must merge, not blow up with a 500."""
    from sqlalchemy.exc import IntegrityError

    from app.services import search_service

    _install(monkeypatch, {"saramin": WorkingCollector()})
    real_merge = search_service._merge_and_commit
    calls = {"n": 0}

    def flaky_merge(db, jobs, keywords):
        calls["n"] += 1
        if calls["n"] == 1:
            # another request committed this fingerprint a moment ago
            real_merge(db, jobs, keywords)
            raise IntegrityError("UNIQUE constraint failed: jobs.fingerprint", None, Exception())
        return real_merge(db, jobs, keywords)

    monkeypatch.setattr(search_service, "_merge_and_commit", flaky_merge)

    response = client.post("/api/search", json={"keywords": ["베트남어"], "sources": ["saramin"]})
    assert response.status_code == 200
    assert len(response.json()["jobs"]) == 1
    assert calls["n"] == 2  # it retried


def test_unknown_source_names_are_ignored(client, monkeypatch, no_demo_mode):
    _install(monkeypatch, {"saramin": WorkingCollector()})
    body = client.post(
        "/api/search", json={"keywords": ["x"], "sources": ["saramin", "does-not-exist"]}
    ).json()
    assert {s["source"] for s in body["sources"]} == {"saramin"}


def test_all_sources_failing_still_returns_200(client, monkeypatch, no_demo_mode):
    _install(monkeypatch, {"wanted": ExplodingCollector()})
    response = client.post("/api/search", json={"keywords": ["x"], "sources": ["wanted"]})
    assert response.status_code == 200
    assert response.json()["jobs"] == []
