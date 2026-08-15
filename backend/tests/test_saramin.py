"""사람인 official Open API collector.

Fixtures mirror the documented response shape at
https://oapi.saramin.co.kr/guide/job-search — no test calls the real API,
and no real key appears anywhere in this repo.
"""

from __future__ import annotations

import httpx
import pytest

from app.collectors.base import CollectorError, SourceStatus
from app.collectors.saramin import (
    API_URL,
    MAX_COUNT,
    SaraminCollector,
    page_to_start,
)
from app.services.dedup_service import deduplicate
from tests.conftest import FakeResponse

TEST_KEY = "test-access-key-not-real"


@pytest.fixture
def with_key(monkeypatch):
    monkeypatch.setattr("app.collectors.saramin.settings.saramin_api_key", TEST_KEY)


def job_row(job_id: str = "36314892", **overrides) -> dict:
    """One job exactly as the guide documents it."""
    row = {
        "id": job_id,
        "url": f"https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx={job_id}",
        "active": 1,
        "posting-timestamp": "1559182220",
        "posting-date": "2019-05-30T11:10:20+09:00",
        "modification-timestamp": "1559182220",
        "opening-timestamp": "1559181600",
        # 2019-06-29T23:59:59+09:00 - the guide's own sample pairs this date with
        # a timestamp of 1988118000 (2033), which contradicts it; we use the
        # consistent value here and cover the far-future case separately below.
        "expiration-timestamp": "1561820399",
        "expiration-date": "2019-06-29T23:59:59+0900",
        "close-type": {"code": "1", "name": "접수마감일"},
        "company": {"detail": {"href": "https://www.saramin.co.kr/x", "name": "테스트주식회사"}},
        "position": {
            "title": "베트남어 통역 담당자",
            "industry": {"code": "301", "name": "무역·상사"},
            "location": {"code": "101050", "name": "서울 > 강남구"},
            "job-type": {"code": "1", "name": "정규직"},
            "job-mid-code": {"code": "22", "name": "무역·유통"},
            "job-code": {"code": "2323", "name": "통역·번역"},
            "experience-level": {"code": 2, "min": 2, "max": 3, "name": "경력 2~3년"},
            "required-education-level": {"code": "0", "name": "학력무관"},
        },
        "keyword": "베트남어,통역,무역",
        "salary": {"code": "6", "name": "3,500만원"},
        "read-cnt": "100",
        "apply-cnt": "50",
    }
    row.update(overrides)
    return row


def payload(*rows, total: str = "95870", start: int = 0) -> dict:
    return {"jobs": {"count": len(rows), "start": start, "total": total, "job": list(rows)}}


def error_payload(code: int, message: str = "error") -> dict:
    return {"code": code, "message": message}


# ------------------------------------------------------------ 1. valid parse


def test_parses_a_valid_response(with_key, fake_http):
    fake_http(FakeResponse(json_data=payload(job_row())))
    jobs = SaraminCollector().collect("베트남어")

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "saramin"
    assert job.source_job_id == "36314892"
    assert job.title == "베트남어 통역 담당자"
    assert job.company == "테스트주식회사"
    assert job.url.startswith("https://www.saramin.co.kr/")
    assert job.is_mock is False


def test_request_targets_the_official_endpoint_with_json(with_key, fake_http):
    fake = fake_http(FakeResponse(json_data=payload(job_row())))
    SaraminCollector().collect("베트남어", limit=100)

    url, params = fake.calls[0]
    assert url == API_URL
    assert params["access-key"] == TEST_KEY
    assert params["keywords"] == "베트남어"
    assert params["count"] == 100
    assert params["start"] == 0
    assert params["sort"] == "pd"


def test_count_is_capped_at_the_documented_maximum(with_key):
    params = SaraminCollector().build_params("베트남어", limit=500)
    assert params["count"] == MAX_COUNT


# ------------------------------------------------------------ 2. empty jobs


def test_parses_an_empty_result_set(with_key, fake_http):
    fake_http(FakeResponse(json_data={"jobs": {"count": 0, "start": 0, "total": "0", "job": []}}))
    assert SaraminCollector().collect("존재하지않는키워드") == []


def test_parses_a_response_with_no_job_key(with_key, fake_http):
    fake_http(FakeResponse(json_data={"jobs": {"count": 0, "start": 0, "total": "0"}}))
    assert SaraminCollector().collect("x") == []


def test_a_single_result_collapsed_to_an_object_is_handled(with_key, fake_http):
    fake_http(FakeResponse(json_data={"jobs": {"count": 1, "job": job_row()}}))
    assert len(SaraminCollector().collect("베트남어")) == 1


# --------------------------------------------------------- 3. invalid shapes


def test_non_json_body_is_an_api_error(with_key, fake_http):
    fake_http(FakeResponse(text="<html>maintenance</html>", json_data=None))
    collector = SaraminCollector()
    # FakeResponse.json() returns None -> not a dict with "jobs"
    with pytest.raises(CollectorError) as caught:
        collector.search("베트남어")
    assert caught.value.status == SourceStatus.API_ERROR


def test_missing_jobs_object_is_an_api_error(with_key, fake_http):
    fake_http(FakeResponse(json_data={"unexpected": True}))
    with pytest.raises(CollectorError) as caught:
        SaraminCollector().search("베트남어")
    assert caught.value.status == SourceStatus.API_ERROR
    assert "jobs" in str(caught.value)


def test_job_list_of_the_wrong_type_is_an_api_error(with_key, fake_http):
    fake_http(FakeResponse(json_data={"jobs": {"job": "not-a-list"}}))
    with pytest.raises(CollectorError) as caught:
        SaraminCollector().search("베트남어")
    assert caught.value.status == SourceStatus.API_ERROR


def test_a_row_without_a_title_is_dropped_not_fatal(with_key, fake_http):
    broken = job_row("999")
    broken["position"] = {}
    fake_http(FakeResponse(json_data=payload(job_row(), broken)))
    jobs = SaraminCollector().collect("베트남어")
    assert [job.source_job_id for job in jobs] == ["36314892"]


def test_network_failure_becomes_a_typed_error(with_key, monkeypatch):
    class Boom:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def get(self, *_args, **_kwargs):
            raise httpx.ConnectError("no route to host")

    monkeypatch.setattr("app.collectors.base.JobCollector._client", lambda self: Boom())
    with pytest.raises(CollectorError) as caught:
        SaraminCollector().search("베트남어")
    assert caught.value.status == SourceStatus.ERROR


# ------------------------------------------------------- 4/5. key handling


def test_missing_api_key_reports_not_configured():
    collector = SaraminCollector()
    assert collector.is_available() is False
    assert collector.unavailable_status() == SourceStatus.NOT_CONFIGURED
    assert "SARAMIN_API_KEY" in collector.unavailable_reason


def test_available_once_the_key_is_set(with_key):
    assert SaraminCollector().is_available() is True


@pytest.mark.parametrize(
    "code,expected",
    [
        (1, SourceStatus.NOT_CONFIGURED),
        (2, SourceStatus.INVALID_KEY),
        (3, SourceStatus.INVALID_REQUEST),
        (4, SourceStatus.RATE_LIMITED),
        (99, SourceStatus.API_ERROR),
        (12345, SourceStatus.API_ERROR),  # undocumented code
    ],
)
def test_documented_error_codes_map_to_statuses(with_key, fake_http, code, expected):
    fake_http(FakeResponse(json_data=error_payload(code, "메시지")))
    with pytest.raises(CollectorError) as caught:
        SaraminCollector().search("베트남어")
    assert caught.value.status == expected
    assert str(code) in caught.value.message


def test_invalid_key_error_carries_the_api_message(with_key, fake_http):
    fake_http(FakeResponse(json_data=error_payload(2, "Invalid access-key")))
    with pytest.raises(CollectorError) as caught:
        SaraminCollector().search("베트남어")
    assert caught.value.status == SourceStatus.INVALID_KEY
    assert "Invalid access-key" in caught.value.message


def test_http_error_status_without_a_body_code(with_key, fake_http):
    fake_http(FakeResponse(json_data={"something": "else"}, status_code=503))
    with pytest.raises(CollectorError) as caught:
        SaraminCollector().search("베트남어")
    assert caught.value.status == SourceStatus.API_ERROR


# ------------------------------------------------------------ 6. pagination


def test_page_to_start_uses_the_documented_zero_based_page_index():
    # the guide defines `start` as a page number, not a record offset
    assert page_to_start(1, 20) == 0
    assert page_to_start(2, 20) == 1
    assert page_to_start(5, 100) == 4
    assert page_to_start(0, 20) == 0


def test_start_and_count_are_forwarded(with_key, fake_http):
    fake = fake_http(FakeResponse(json_data=payload(job_row())))
    SaraminCollector().collect("베트남어", limit=20, start=page_to_start(3, 20))
    _url, params = fake.calls[0]
    assert params["start"] == 2
    assert params["count"] == 20


def test_negative_start_is_clamped(with_key):
    assert SaraminCollector().build_params("x", start=-5)["start"] == 0


# ---------------------------------------------------------- 7. normalization


def test_normalization_maps_every_documented_field(with_key, fake_http):
    fake_http(FakeResponse(json_data=payload(job_row())))
    job = SaraminCollector().collect("베트남어")[0]

    assert job.location == "서울 > 강남구"
    assert job.location_region == "서울"
    assert job.employment_type == "정규직"          # position.job-type.name
    assert job.experience == "경력"                  # experience-level.name "경력 2~3년"
    assert job.education == "학력무관"               # required-education-level.name
    assert job.salary == "3,500만원"                 # salary.name
    assert job.salary_code == "6"                    # salary.code
    assert job.salary_value == 3500
    assert job.description == "통역·번역"            # job-code.name
    assert job.keywords == "베트남어,통역,무역"      # job.keyword
    assert job.is_active is True
    assert job.posted_at is not None
    assert job.deadline is not None
    assert job.posted_at.tzinfo is None              # sqlite stores naive datetimes


def test_a_far_future_expiration_means_always_open(with_key, fake_http):
    """1988118000 (2033) is a sentinel, not a deadline a job seeker can act on."""
    fake_http(FakeResponse(json_data=payload(job_row(**{"expiration-timestamp": "1988118000"}))))
    job = SaraminCollector().collect("베트남어")[0]
    assert job.deadline is None
    assert job.posted_at is not None  # the posting date is still read


def test_inactive_posting_is_flagged(with_key, fake_http):
    fake_http(FakeResponse(json_data=payload(job_row(active=0))))
    assert SaraminCollector().collect("베트남어")[0].is_active is False


def test_missing_company_name_falls_back(with_key, fake_http):
    fake_http(FakeResponse(json_data=payload(job_row(company={"detail": {}}))))
    assert SaraminCollector().collect("베트남어")[0].company == "회사명 비공개"


def test_unparsable_salary_keeps_its_text(with_key, fake_http):
    row = job_row(salary={"code": "0", "name": "회사내규에 따름"})
    fake_http(FakeResponse(json_data=payload(row)))
    job = SaraminCollector().collect("베트남어")[0]
    assert job.salary == "회사내규에 따름"
    assert job.salary_value is None


# -------------------------------------------------------- 8. deduplication


def test_the_same_posting_twice_collapses_to_one(with_key, fake_http):
    fake_http(FakeResponse(json_data=payload(job_row(), job_row())))
    jobs = SaraminCollector().collect("베트남어")
    assert len(jobs) == 2                    # the collector returns what the API sent
    assert len(deduplicate(jobs)) == 1       # dedup collapses them on source_job_id


def test_distinct_postings_are_kept(with_key, fake_http):
    other = job_row("777")
    other["position"] = dict(job_row()["position"], title="외국인 생산직")
    other["company"] = {"detail": {"name": "다른회사"}}
    fake_http(FakeResponse(json_data=payload(job_row(), other)))
    assert len(deduplicate(SaraminCollector().collect("베트남어"))) == 2


# ------------------------------------------------- supported search filters


def test_mvp_filters_are_forwarded(with_key):
    params = SaraminCollector().build_params(
        "베트남어",
        loc_cd="101000",
        job_type="1",
        job_cd=["2323", "2324"],
        published="2026-08-01",
    )
    assert params["loc_cd"] == "101000"
    assert params["job_type"] == "1"
    assert params["job_cd"] == "2323,2324"   # multi-value filters are comma separated
    assert params["published"] == "2026-08-01"


def test_unsupported_parameters_are_dropped(with_key):
    params = SaraminCollector().build_params("베트남어", not_a_real_param="x")
    assert "not_a_real_param" not in params


def test_empty_filters_are_omitted(with_key):
    params = SaraminCollector().build_params("베트남어", loc_cd=None, job_cd=[], job_type="")
    assert "loc_cd" not in params and "job_cd" not in params and "job_type" not in params


def test_invalid_sort_falls_back_to_pd(with_key):
    assert SaraminCollector().build_params("x", sort="bogus")["sort"] == "pd"
    assert SaraminCollector().build_params("x", sort="ac")["sort"] == "ac"


def test_no_real_key_is_committed():
    """Guard against a real key sneaking into the fixtures."""
    assert TEST_KEY.startswith("test-")
