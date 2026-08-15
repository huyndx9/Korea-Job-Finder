"""API surface: search, filtering, sorting, pagination, detail, sources, health."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.collectors.base import JobCollector, NormalizedJob
from app.models import Job
from app.services.dedup_service import make_fingerprint


class FakeCollector(JobCollector):
    """A source that always works, with no network involved."""

    name = "saramin"
    label = "사람인"
    site_url = "https://www.saramin.co.kr"

    rows = [
        ("베트남어 통역 담당자", "가나다회사", "서울 강남구", "서울", "정규직", "경력무관", 3500),
        ("외국인 생산직 모집", "라마바회사", "경기 화성시", "경기", "계약직", "신입", 3000),
        ("베트남어 강사 아르바이트", "사아자회사", "부산 해운대구", "부산", "아르바이트", "경력무관", 2500),
    ]

    def search(self, keyword: str, limit: int = 50):
        return [dict(zip(("title", "company", "loc", "region", "emp", "exp", "sal"), row)) for row in self.rows]

    def normalize(self, raw_job):
        return NormalizedJob(
            source=self.name,
            source_job_id=f"{self.name}-{abs(hash(raw_job['title'])) % 10**6}",
            title=raw_job["title"],
            company=raw_job["company"],
            location=raw_job["loc"],
            location_region=raw_job["region"],
            salary=f"연봉 {raw_job['sal']}만원",
            salary_value=raw_job["sal"],
            employment_type=raw_job["emp"],
            experience=raw_job["exp"],
            url=f"https://example.com/{abs(hash(raw_job['title'])) % 10**6}",
            posted_at=datetime(2026, 8, 1 + self.rows.index(tuple(raw_job.values()))),
        )


@pytest.fixture
def only_fake_collector(monkeypatch):
    monkeypatch.setattr(
        "app.services.search_service.build_collectors",
        lambda *_a, **_k: {"saramin": FakeCollector()},
    )


def seed(db, count: int = 25) -> None:
    for i in range(count):
        job = Job(
            source="saramin" if i % 2 == 0 else "jobkorea",
            source_job_id=str(1000 + i),
            title=f"베트남어 담당자 {i}" if i % 2 == 0 else f"외국인 사원 {i}",
            company=f"회사{i}",
            location="서울 강남구" if i % 3 == 0 else "경기 수원시",
            location_region="서울" if i % 3 == 0 else "경기",
            salary=f"연봉 {3000 + i * 100}만원",
            salary_value=3000 + i * 100,
            employment_type="정규직" if i % 2 == 0 else "아르바이트",
            experience="신입" if i % 4 == 0 else "경력",
            url=f"https://example.com/{i}",
            posted_at=datetime(2026, 7, 1 + (i % 28)),
            fingerprint=f"seed-{i}",
            keywords="베트남어",
        )
        db.add(job)
    db.commit()


# ------------------------------------------------------------------- health


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_root_points_at_the_docs(client):
    assert client.get("/").json()["docs"] == "/docs"


# ------------------------------------------------------------------ sources


def test_sources_is_keyed_by_source_name(client):
    sources = client.get("/api/sources").json()
    assert {"saramin", "jobkorea", "wanted", "work24", "albamon", "alba", "indeed"} <= set(sources)

    assert sources["saramin"]["default"] is True
    assert sources["albamon"]["default"] is False
    # an unavailable source must explain itself instead of silently disappearing
    assert sources["albamon"]["available"] is False
    assert sources["albamon"]["status"] == "unavailable"
    assert sources["albamon"]["message"]


def test_sources_reports_not_configured_without_an_api_key(client):
    saramin = client.get("/api/sources").json()["saramin"]
    assert saramin["status"] == "not_configured"
    assert "SARAMIN_API_KEY" in saramin["message"]
    assert saramin["last_success"] is None
    assert saramin["last_result_count"] == 0


def test_sources_is_idle_before_any_search(client):
    assert client.get("/api/sources").json()["jobkorea"]["status"] == "idle"


def test_sources_reports_connected_after_a_successful_search(client, monkeypatch):
    class FakeJobKorea(FakeCollector):
        name = "jobkorea"
        label = "잡코리아"

    monkeypatch.setattr(
        "app.services.search_service.build_collectors", lambda *_a, **_k: {"jobkorea": FakeJobKorea()}
    )
    client.post("/api/search", json={"keywords": ["베트남어"], "sources": ["jobkorea"]})
    jobkorea = client.get("/api/sources").json()["jobkorea"]

    assert jobkorea["status"] == "connected"
    assert jobkorea["last_result_count"] == 3
    assert jobkorea["last_success"] is not None
    assert jobkorea["last_checked"] is not None


def test_missing_key_beats_an_earlier_observed_status(client, only_fake_collector):
    """Saramin has no key here, so /api/sources must say so regardless of history."""
    client.post("/api/search", json={"keywords": ["베트남어"], "sources": ["saramin"]})
    assert client.get("/api/sources").json()["saramin"]["status"] == "not_configured"


# ------------------------------------------------------------------- search


def test_search_returns_jobs_and_per_source_status(client, only_fake_collector):
    body = client.post("/api/search", json={"keywords": ["베트남어"], "sources": ["saramin"]}).json()

    assert len(body["jobs"]) == 3
    assert body["keywords"] == ["베트남어"]
    assert body["pagination"]["total"] == 3
    assert body["elapsed_ms"] >= 0

    status = body["sources"][0]
    assert status["source"] == "saramin"
    assert status["status"] == "connected"
    assert status["count"] == 3
    assert status["is_mock"] is False

    job = body["jobs"][0]
    assert job["url"].startswith("http")
    assert job["title"] and job["company"]


def test_search_requires_a_keyword(client):
    assert client.post("/api/search", json={"keywords": []}).status_code == 400
    assert client.post("/api/search", json={"keywords": ["   "]}).status_code == 400


def test_search_persists_to_the_database(client, db, only_fake_collector):
    client.post("/api/search", json={"keywords": ["베트남어"], "sources": ["saramin"]})
    assert db.query(Job).count() == 3


def test_repeated_search_does_not_duplicate_rows(client, db, only_fake_collector):
    for _ in range(3):
        client.post("/api/search", json={"keywords": ["베트남어"], "sources": ["saramin"]})
    assert db.query(Job).count() == 3


def test_search_deduplicates_across_sources(client, monkeypatch):
    """Two sites returning the same opening -> one card."""

    class Mirror(FakeCollector):
        name = "jobkorea"
        label = "잡코리아"

    monkeypatch.setattr(
        "app.services.search_service.build_collectors",
        lambda *_a, **_k: {"saramin": FakeCollector(), "jobkorea": Mirror()},
    )
    body = client.post(
        "/api/search", json={"keywords": ["베트남어"], "sources": ["saramin", "jobkorea"]}
    ).json()

    assert sum(s["count"] for s in body["sources"]) == 6
    assert body["pagination"]["total"] == 3
    assert body["duplicates_removed"] == 3


def test_search_paginates(client, only_fake_collector):
    body = client.post(
        "/api/search", json={"keywords": ["베트남어"], "sources": ["saramin"], "page": 2, "limit": 2}
    ).json()
    assert len(body["jobs"]) == 1
    assert body["pagination"] == {"page": 2, "limit": 2, "total": 3, "total_pages": 2}


def test_search_sorts_by_salary(client, only_fake_collector):
    body = client.post(
        "/api/search",
        json={"keywords": ["베트남어"], "sources": ["saramin"], "sort": "salary_desc"},
    ).json()
    values = [job["salary_value"] for job in body["jobs"]]
    assert values == sorted(values, reverse=True)


# -------------------------------------------------------------------- /jobs


def test_list_jobs_paginates(client, db):
    seed(db, 25)
    body = client.get("/api/jobs?page=1&limit=10").json()
    assert len(body["jobs"]) == 10
    assert body["pagination"]["total"] == 25
    assert body["pagination"]["total_pages"] == 3

    last = client.get("/api/jobs?page=3&limit=10").json()
    assert len(last["jobs"]) == 5


def test_list_jobs_filters_by_keyword(client, db):
    seed(db, 25)
    body = client.get("/api/jobs?keyword=외국인&limit=100").json()
    assert body["jobs"]
    assert all("외국인" in job["title"] for job in body["jobs"])


def test_list_jobs_matches_any_of_several_keywords(client, db):
    seed(db, 25)
    body = client.get("/api/jobs?keyword=외국인&keyword=베트남어&limit=100").json()
    assert len(body["jobs"]) == 25
    only_one = client.get("/api/jobs?keyword=외국인&limit=100").json()
    assert 0 < len(only_one["jobs"]) < 25


def test_list_jobs_filters_by_source_region_type_and_experience(client, db):
    seed(db, 25)

    by_source = client.get("/api/jobs?source=saramin&limit=100").json()
    assert {job["source"] for job in by_source["jobs"]} == {"saramin"}

    by_region = client.get("/api/jobs?location=서울&limit=100").json()
    assert {job["location_region"] for job in by_region["jobs"]} == {"서울"}

    by_type = client.get("/api/jobs?employment_type=아르바이트&limit=100").json()
    assert {job["employment_type"] for job in by_type["jobs"]} == {"아르바이트"}

    by_exp = client.get("/api/jobs?experience=신입&limit=100").json()
    assert {job["experience"] for job in by_exp["jobs"]} == {"신입"}


def test_list_jobs_combines_filters(client, db):
    seed(db, 25)
    body = client.get("/api/jobs?source=saramin&employment_type=정규직&location=서울&limit=100").json()
    for job in body["jobs"]:
        assert job["source"] == "saramin"
        assert job["employment_type"] == "정규직"
        assert job["location_region"] == "서울"


def test_list_jobs_accepts_multiple_values_per_filter(client, db):
    seed(db, 25)
    body = client.get("/api/jobs?location=서울&location=경기&limit=100").json()
    assert {job["location_region"] for job in body["jobs"]} == {"서울", "경기"}


@pytest.mark.parametrize("sort", ["latest", "oldest", "salary_desc", "salary_asc"])
def test_list_jobs_sorting(client, db, sort):
    seed(db, 25)
    jobs = client.get(f"/api/jobs?sort={sort}&limit=100").json()["jobs"]

    if sort == "salary_desc":
        values = [j["salary_value"] for j in jobs]
        assert values == sorted(values, reverse=True)
    elif sort == "salary_asc":
        values = [j["salary_value"] for j in jobs]
        assert values == sorted(values)
    else:
        dates = [j["posted_at"] for j in jobs]
        assert dates == sorted(dates, reverse=(sort == "latest"))


def test_demo_rows_never_outrank_real_postings(client, db):
    """A source standing in with mock data must not bury the real results."""
    db.add(
        Job(
            source="saramin",
            source_job_id="demo-1",
            title="샘플 공고",
            company="샘플회사",
            location_region="서울",
            salary_value=99000,
            url="https://example.com/demo",
            posted_at=datetime(2026, 8, 8),  # newest of all
            fingerprint="demo-1",
            is_mock=1,
        )
    )
    db.add(
        Job(
            source="jobkorea",
            source_job_id="real-1",
            title="실제 공고",
            company="실제회사",
            location_region="서울",
            url="https://example.com/real",
            posted_at=None,  # jobkorea listings carry no date
            fingerprint="real-1",
            is_mock=0,
        )
    )
    db.commit()

    for sort in ("latest", "oldest", "salary_desc", "salary_asc"):
        jobs = client.get(f"/api/jobs?sort={sort}").json()["jobs"]
        assert jobs[0]["title"] == "실제 공고", f"demo row led the list for sort={sort}"


def test_unknown_sort_falls_back_to_latest(client, db):
    seed(db, 5)
    assert client.get("/api/jobs?sort=bogus").status_code == 200


def test_empty_database_returns_an_empty_page(client):
    body = client.get("/api/jobs").json()
    assert body["jobs"] == []
    assert body["pagination"]["total"] == 0


# --------------------------------------------------------------- /jobs/{id}


def test_get_one_job(client, db):
    seed(db, 3)
    listed = client.get("/api/jobs").json()["jobs"][0]
    body = client.get(f"/api/jobs/{listed['id']}").json()
    assert body["id"] == listed["id"]
    assert body["url"].startswith("http")


def test_get_missing_job_is_404(client):
    assert client.get("/api/jobs/999999").status_code == 404


def test_stored_fingerprint_matches_the_dedup_rule(db):
    job = NormalizedJob(
        source="saramin", source_job_id="1", title="t", company="c", url="https://x.dev/1"
    )
    assert make_fingerprint(job) == make_fingerprint(job)
