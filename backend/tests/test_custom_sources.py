"""Job sites added by hand: config -> working collector, and the guards around it."""

from __future__ import annotations

import pytest

from app.collectors.custom import CustomCollector, dig
from app.models.custom_source import CustomSource
from app.utils.url_guard import UnsafeUrlError, validate_search_url
from tests.conftest import FakeResponse

HTML_PAGE = """
<html><body>
  <ul class="jobs">
    <li class="job">
      <a class="title" href="/jobs/12345">베트남어 통역 담당자</a>
      <span class="corp">테스트무역</span>
      <span class="loc">서울 강남구</span>
      <span class="pay">연봉 3,500만원</span>
      <span class="when">2026-08-01</span>
      <p class="desc">정규직 · 경력무관 · 통역 업무</p>
    </li>
    <li class="job">
      <a class="title" href="/jobs/67890">외국인 생산직 모집</a>
      <span class="corp">대한정밀</span>
      <span class="loc">경기 화성시</span>
      <span class="pay">월급 280만원</span>
      <span class="when">2026-08-02</span>
      <p class="desc">계약직 · 신입</p>
    </li>
    <li class="job"><span class="corp">제목 없는 항목</span></li>
  </ul>
</body></html>
"""

JSON_PAYLOAD = {
    "result": {
        "positions": [
            {
                "id": 555,
                "title": "베트남어 마케터",
                "companyName": "글로벌미디어",
                "address": {"location": "서울 마포구"},
                "salary": {"name": "연봉 4,000만원"},
                "created_at": "2026-08-03T09:00:00+09:00",
                "category": "마케팅",
            },
            {"id": 556, "title": "", "companyName": "무제"},  # dropped: no title
        ]
    }
}


def html_config(**overrides) -> CustomSource:
    config = CustomSource(
        name="mysite",
        label="마이사이트",
        kind="html",
        site_url="https://example.com",
        search_url="https://example.com/search?q={keyword}",
        item_selector="li.job",
        title_selector="a.title",
        company_selector=".corp",
        location_selector=".loc",
        salary_selector=".pay",
        date_selector=".when",
        description_selector=".desc",
        link_selector="a.title",
        enabled=True,
    )
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def json_config(**overrides) -> CustomSource:
    config = CustomSource(
        name="myapi",
        label="마이API",
        kind="json",
        site_url="https://example.com",
        search_url="https://example.com/api/jobs?q={keyword}",
        item_selector="result.positions",
        title_selector="title",
        company_selector="companyName",
        location_selector="address.location",
        salary_selector="salary.name",
        date_selector="created_at",
        description_selector="category",
        link_selector="id",
        link_template="https://example.com/jobs/{value}",
        enabled=True,
    )
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


# ------------------------------------------------------------------ dotted path


@pytest.mark.parametrize(
    "path,expected",
    [
        ("result.positions.0.title", "베트남어 마케터"),
        ("result.positions.0.address.location", "서울 마포구"),
        ("result.missing", None),
        ("result.positions.9.title", None),
        ("", None),
    ],
)
def test_dig_follows_dotted_paths(path, expected):
    assert dig(JSON_PAYLOAD, path) == expected


# ------------------------------------------------------------------ HTML mode


def test_html_source_parses_and_normalizes(fake_http):
    fake_http(FakeResponse(text=HTML_PAGE))
    jobs = CustomCollector(html_config()).collect("베트남어")

    assert len(jobs) == 2  # the title-less row was dropped
    first = jobs[0]
    assert first.source == "mysite"
    assert first.title == "베트남어 통역 담당자"
    assert first.company == "테스트무역"
    assert first.location == "서울 강남구"
    assert first.location_region == "서울"
    assert first.salary_value == 3500
    assert first.employment_type == "정규직"   # inferred from the description
    assert first.experience == "경력무관"
    assert first.url == "https://example.com/jobs/12345"
    assert first.source_job_id == "12345"
    assert first.posted_at is not None
    assert first.is_mock is False


def test_html_link_falls_back_to_the_first_anchor(fake_http):
    fake_http(FakeResponse(text=HTML_PAGE))
    jobs = CustomCollector(html_config(link_selector=None)).collect("베트남어")
    assert jobs[0].url == "https://example.com/jobs/12345"


def test_html_missing_optional_selectors_still_works(fake_http):
    fake_http(FakeResponse(text=HTML_PAGE))
    config = html_config(
        company_selector=None, location_selector=None, salary_selector=None, date_selector=None
    )
    job = CustomCollector(config).collect("베트남어")[0]
    assert job.title == "베트남어 통역 담당자"
    assert job.company == "회사명 비공개"


def test_item_selector_that_matches_nothing_returns_empty(fake_http):
    fake_http(FakeResponse(text=HTML_PAGE))
    assert CustomCollector(html_config(item_selector="div.nope")).collect("베트남어") == []


# ------------------------------------------------------------------ JSON mode


def test_json_source_parses_and_normalizes(fake_http):
    fake_http(FakeResponse(json_data=JSON_PAYLOAD))
    jobs = CustomCollector(json_config()).collect("베트남어")

    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "베트남어 마케터"
    assert job.company == "글로벌미디어"
    assert job.location == "서울 마포구"
    assert job.salary_value == 4000
    assert job.url == "https://example.com/jobs/555"
    assert job.description == "마케팅"


def test_json_path_pointing_at_a_non_list_is_reported(fake_http):
    from app.collectors.base import CollectorError, SourceStatus

    fake_http(FakeResponse(json_data=JSON_PAYLOAD))
    with pytest.raises(CollectorError) as caught:
        CustomCollector(json_config(item_selector="result")).search("x")
    assert caught.value.status == SourceStatus.INVALID_REQUEST


def test_url_is_built_from_the_keyword():
    collector = CustomCollector(html_config())
    assert collector.build_url("베트남어").endswith("q=%EB%B2%A0%ED%8A%B8%EB%82%A8%EC%96%B4")


def test_disabled_source_is_unavailable():
    collector = CustomCollector(html_config(enabled=False))
    assert collector.is_available() is False


# --------------------------------------------------------------- URL guard


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000/x?q={keyword}",
        "http://127.0.0.1/{keyword}",
        "http://169.254.169.254/latest/meta-data/{keyword}",   # cloud metadata
        "http://[::1]/{keyword}",
        "file:///etc/passwd?q={keyword}",
        "ftp://example.com/{keyword}",
        "https://user:pass@example.com/{keyword}",
    ],
)
def test_unsafe_urls_are_rejected(url):
    with pytest.raises(UnsafeUrlError):
        validate_search_url(url)


def test_url_without_the_placeholder_is_rejected():
    with pytest.raises(UnsafeUrlError, match=r"\{keyword\}"):
        validate_search_url("https://example.com/search?q=hardcoded")


def test_a_public_url_passes():
    assert validate_search_url("https://example.com/search?q={keyword}")


def test_rejection_message_names_the_address():
    with pytest.raises(UnsafeUrlError, match="non-public"):
        validate_search_url("http://127.0.0.1/{keyword}")


# ------------------------------------------------------------------- the API


PAYLOAD = {
    "name": "mysite",
    "label": "마이사이트",
    "kind": "html",
    "site_url": "https://example.com",
    "search_url": "https://example.com/search?q={keyword}",
    "item_selector": "li.job",
    "title_selector": "a.title",
    "company_selector": ".corp",
    "link_selector": "a.title",
}


def test_create_list_and_delete(client):
    assert client.get("/api/sources/custom").json() == []

    created = client.post("/api/sources/custom", json=PAYLOAD)
    assert created.status_code == 201
    assert created.json()["name"] == "mysite"

    assert len(client.get("/api/sources/custom").json()) == 1
    # it joins the main source list, flagged as user-added
    listed = client.get("/api/sources").json()
    assert listed["mysite"]["custom"] is True
    assert listed["mysite"]["status"] == "idle"
    assert listed["saramin"]["custom"] is False

    assert client.delete("/api/sources/custom/mysite").status_code == 204
    assert "mysite" not in client.get("/api/sources").json()


def test_duplicate_name_is_rejected(client):
    client.post("/api/sources/custom", json=PAYLOAD)
    assert client.post("/api/sources/custom", json=PAYLOAD).status_code == 409


def test_built_in_names_are_reserved(client):
    assert client.post("/api/sources/custom", json={**PAYLOAD, "name": "saramin"}).status_code == 422


@pytest.mark.parametrize("name", ["x", "has space", "1", "", "-starts-with-dash", "왜한글"])
def test_invalid_slugs_are_rejected(client, name):
    assert client.post("/api/sources/custom", json={**PAYLOAD, "name": name}).status_code == 422


def test_uppercase_names_are_normalized_not_rejected(client):
    created = client.post("/api/sources/custom", json={**PAYLOAD, "name": "My-Site"})
    assert created.status_code == 201
    assert created.json()["name"] == "my-site"


def test_unsafe_url_is_rejected_by_the_api(client):
    response = client.post(
        "/api/sources/custom", json={**PAYLOAD, "search_url": "http://127.0.0.1/{keyword}"}
    )
    assert response.status_code == 400
    assert "non-public" in response.json()["detail"]


def test_update_toggles_enabled(client):
    client.post("/api/sources/custom", json=PAYLOAD)
    assert client.patch("/api/sources/custom/mysite", json={"enabled": False}).json()["enabled"] is False
    assert client.get("/api/sources").json()["mysite"]["status"] == "unavailable"


def test_update_rejects_an_unsafe_url(client):
    client.post("/api/sources/custom", json=PAYLOAD)
    response = client.patch(
        "/api/sources/custom/mysite", json={"search_url": "http://localhost/{keyword}"}
    )
    assert response.status_code == 400


def test_update_and_delete_of_a_missing_source_are_404(client):
    assert client.patch("/api/sources/custom/ghost", json={"enabled": True}).status_code == 404
    assert client.delete("/api/sources/custom/ghost").status_code == 404


def test_preview_parses_without_saving(client, fake_http):
    fake_http(FakeResponse(text=HTML_PAGE))
    body = client.post("/api/sources/custom/test", json={**PAYLOAD, "keyword": "베트남어"}).json()

    assert body["ok"] is True
    assert body["items_found"] == 3
    assert body["jobs_parsed"] == 2
    assert body["jobs"][0]["title"] == "베트남어 통역 담당자"
    assert "%EB%B2%A0" in body["requested_url"]  # the keyword was substituted
    # nothing was persisted
    assert client.get("/api/sources/custom").json() == []


def test_preview_explains_a_selector_that_matches_nothing(client, fake_http):
    fake_http(FakeResponse(text=HTML_PAGE))
    body = client.post(
        "/api/sources/custom/test", json={**PAYLOAD, "item_selector": "div.nope"}
    ).json()
    assert body["ok"] is False
    assert body["items_found"] == 0
    assert body["message"]


def test_preview_explains_items_found_but_unreadable(client, fake_http):
    fake_http(FakeResponse(text=HTML_PAGE))
    body = client.post(
        "/api/sources/custom/test", json={**PAYLOAD, "title_selector": ".not-there"}
    ).json()
    assert body["ok"] is False
    assert body["items_found"] == 3
    assert body["jobs_parsed"] == 0


def test_preview_reports_a_failed_request_instead_of_raising(client, monkeypatch):
    import httpx

    class Boom:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def get(self, *_args, **_kwargs):
            raise httpx.ConnectError("nope")

    monkeypatch.setattr("app.collectors.base.JobCollector._client", lambda self: Boom())
    body = client.post("/api/sources/custom/test", json=PAYLOAD).json()
    assert body["ok"] is False
    assert body["status"] == "error"


def test_searching_through_a_custom_source(client, fake_http):
    """The whole point: a hand-added site behaves like a built-in one."""
    client.post("/api/sources/custom", json=PAYLOAD)
    fake_http(FakeResponse(text=HTML_PAGE))

    body = client.post("/api/search", json={"keywords": ["베트남어"], "sources": ["mysite"]}).json()
    assert body["sources"][0]["status"] == "connected"
    assert body["sources"][0]["count"] == 2
    assert body["pagination"]["total"] == 2

    stored = client.get("/api/jobs?source=mysite").json()
    assert stored["pagination"]["total"] == 2
    assert all(job["source"] == "mysite" for job in stored["jobs"])


def test_re_searching_a_custom_source_does_not_duplicate(client, fake_http):
    client.post("/api/sources/custom", json=PAYLOAD)
    fake_http(FakeResponse(text=HTML_PAGE))
    for _ in range(3):
        client.post("/api/search", json={"keywords": ["베트남어"], "sources": ["mysite"]})
    assert client.get("/api/jobs?source=mysite").json()["pagination"]["total"] == 2
