"""Collector search + parsing + normalization, against canned responses.

No test here touches the network.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from app.collectors import COLLECTOR_CLASSES, build_collectors, get_collector
from app.collectors.incruit import IncruitCollector
from app.collectors.jobkorea import JobKoreaCollector
from app.collectors.jobploy import JobployCollector
from app.collectors.mock import MockJobCollector
from app.collectors.base import SourceStatus
from app.collectors.placeholders import (
    AlbamonCollector,
    BuddiesKoreaCollector,
    KoworkCollector,
    KWorkCollector,
)
from app.collectors.saramin import SaraminCollector
from app.collectors.wanted import WantedCollector
from app.collectors.work24 import Work24Collector
from tests.conftest import FakeResponse

# --------------------------------------------------------------- mock source


def test_mock_collector_finds_keyword_matches():
    jobs = MockJobCollector().collect("베트남어")
    assert len(jobs) >= 10
    assert all(job.is_mock for job in jobs)
    assert all(job.is_valid() for job in jobs)


def test_mock_collector_matches_by_tag_not_only_title():
    jobs = MockJobCollector().collect("외국인")
    assert len(jobs) >= 10
    assert any("외국인" not in job.title for job in jobs)


def test_mock_collector_synthesizes_for_unknown_keyword():
    jobs = MockJobCollector().collect("용접")
    assert jobs, "the demo must stay useful for keywords outside the fixture set"
    assert all("용접" in job.title for job in jobs)


def test_mock_collector_normalizes_every_field():
    job = next(j for j in MockJobCollector().collect("베트남어") if j.source_job_id == "mock-m001")
    assert job.title == "베트남어 가능 해외영업 담당자 모집"
    assert job.company == "ABC 주식회사"
    assert job.location_region == "서울"
    assert job.employment_type == "정규직"
    assert job.experience == "경력무관"
    assert job.salary_value == 3500
    assert job.url.startswith("https://")


def test_mock_collector_can_stand_in_for_a_real_source():
    jobs = MockJobCollector(as_source="saramin", as_label="사람인").collect("베트남어")
    assert {job.source for job in jobs} == {"saramin"}
    assert all(job.is_mock for job in jobs)
    # the link must go somewhere real, not to a fabricated posting id
    assert all(job.url.startswith("https://www.saramin.co.kr/") for job in jobs)


def test_mock_collector_does_not_mutate_the_shared_fixtures():
    from app.collectors.mock_data import MOCK_JOBS

    MockJobCollector().collect("베트남어")
    assert all("_keyword" not in row for row in MOCK_JOBS)


# ------------------------------------------------------------------ saramin

SARAMIN_PAYLOAD = {
    "jobs": {
        "count": 2,
        "job": [
            {
                "id": "50123456",
                "url": "https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=50123456",
                "company": {"detail": {"name": "테스트주식회사"}},
                "position": {
                    "title": "베트남어 통역 담당자",
                    "location": {"name": "서울 > 강남구"},
                    "job-type": {"name": "정규직"},
                    "experience-level": {"name": "경력무관"},
                    "job-code": {"name": "통역·번역"},
                },
                "salary": {"name": "연봉 3,500만원"},
                "posting-date": "2026-08-01T09:00:00+09:00",
            },
            {  # unusable row: no title -> must be dropped, not crash the page
                "id": "50123457",
                "url": "https://www.saramin.co.kr/x",
                "company": {"detail": {}},
                "position": {},
            },
        ],
    }
}


def test_saramin_is_unavailable_without_an_api_key():
    collector = SaraminCollector()
    assert collector.is_available() is False
    assert "SARAMIN_API_KEY" in collector.unavailable_reason


def test_saramin_parses_and_normalizes(monkeypatch, fake_http):
    monkeypatch.setattr("app.collectors.saramin.settings.saramin_api_key", "test-key")
    fake = fake_http(FakeResponse(json_data=SARAMIN_PAYLOAD))

    collector = SaraminCollector()
    assert collector.is_available() is True

    jobs = collector.collect("베트남어")
    assert len(jobs) == 1  # the title-less row was dropped
    job = jobs[0]
    assert job.source == "saramin"
    assert job.source_job_id == "50123456"
    assert job.title == "베트남어 통역 담당자"
    assert job.company == "테스트주식회사"
    assert job.location_region == "서울"
    assert job.employment_type == "정규직"
    assert job.experience == "경력무관"
    assert job.salary_value == 3500
    assert job.posted_at is not None
    assert job.is_mock is False

    # the keyword really was sent to the API
    _url, params = fake.calls[0]
    assert params["keywords"] == "베트남어"


def test_saramin_handles_a_single_result_collapsed_to_an_object(monkeypatch, fake_http):
    monkeypatch.setattr("app.collectors.saramin.settings.saramin_api_key", "test-key")
    single = {"jobs": {"count": 1, "job": SARAMIN_PAYLOAD["jobs"]["job"][0]}}
    fake_http(FakeResponse(json_data=single))
    assert len(SaraminCollector().collect("베트남어")) == 1


# ------------------------------------------------------------------- wanted

WANTED_PAYLOAD = {
    "data": [
        {
            "id": 367606,
            "position": "[운영팀] 외국인 오퍼레이터 (베트남어)",
            "company": {"name": "하이어다이버시티"},
            "address": {"location": "서울", "district": "강남구"},
            "annual_from": 1,
            "annual_to": 5,
            "category": "고객 서비스",
        },
        {"id": 999, "position": "", "company": {"name": "무제"}},  # dropped: no title
    ]
}


def test_wanted_parses_and_normalizes(fake_http):
    fake_http(FakeResponse(json_data=WANTED_PAYLOAD))
    jobs = WantedCollector().collect("베트남어")

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source_job_id == "367606"
    assert job.title == "[운영팀] 외국인 오퍼레이터 (베트남어)"
    assert job.company == "하이어다이버시티"
    assert job.location == "서울 강남구"
    assert job.location_region == "서울"
    assert job.experience == "경력"
    assert job.url == "https://www.wanted.co.kr/wd/367606"


def test_wanted_treats_zero_years_as_entry_level(fake_http):
    payload = {"data": [dict(WANTED_PAYLOAD["data"][0], annual_from=0, annual_to=0)]}
    fake_http(FakeResponse(json_data=payload))
    assert WantedCollector().collect("x")[0].experience == "신입"


def test_wanted_survives_an_empty_body(fake_http):
    fake_http(FakeResponse(json_data={}))
    assert WantedCollector().collect("베트남어") == []


# ----------------------------------------------------------------- jobkorea

JOBKOREA_HTML = """
<html><body>
  <div class="wrap">
    <div class="w-full rounded-2xl shadow-list">
      <div class="flex w-full gap-5 p-7">
        <a href="/Recruit/GI_Read/49725343?Oem_Code=C1"><img src="x.png"/></a>
        <div class="w-full">
          <button>스크랩</button>
          <div class="mb-0.5">
            <a href="/Recruit/GI_Read/49725343?Oem_Code=C1">베트남어 강사 아르바이트 모집</a>
          </div>
          <a href="/Recruit/Co_Read/C/1234">주식회사 월드브릿지</a>
          <span>서울 영등포구</span><span>시급 12,000원</span><span>경력무관</span>
        </div>
      </div>
    </div>
    <div class="w-full rounded-2xl shadow-list">
      <div class="flex w-full gap-5 p-7">
        <div class="w-full">
          <div class="mb-0.5">
            <a href="/Recruit/GI_Read/49651217">베트남어 가능 사무보조 정규직</a>
          </div>
          <a href="/Recruit/Co_Read/C/5678">건인약품</a>
          <span>경기 안양시</span><span>학원·어학원·교육원, 외국어강사</span><span>경력2년↑</span>
        </div>
      </div>
    </div>
  </div>
</body></html>
"""


def test_jobkorea_parses_cards_from_utility_class_markup(fake_http):
    fake_http(FakeResponse(text=JOBKOREA_HTML))
    jobs = JobKoreaCollector().collect("베트남어")

    assert len(jobs) == 2
    first, second = jobs

    assert first.source_job_id == "49725343"
    assert first.title == "베트남어 강사 아르바이트 모집"
    assert first.company == "주식회사 월드브릿지"
    assert first.location == "서울 영등포구"
    assert first.location_region == "서울"
    assert first.employment_type == "아르바이트"
    assert first.experience == "경력무관"
    assert first.salary_value == round(12000 * 209 * 12 / 10000)
    assert first.url == "https://www.jobkorea.co.kr/Recruit/GI_Read/49725343?Oem_Code=C1"

    assert second.source_job_id == "49651217"
    assert second.company == "건인약품"
    assert second.location_region == "경기"
    assert second.employment_type == "정규직"
    assert second.experience == "경력"
    # 학원 / 교육원 are words, not money
    assert second.salary is None


# the page also ships its results as JSON inside a JS string, where quotes are
# escaped - that payload is the only place a posting date appears
_JOBKOREA_PAYLOAD = (
    r'<script>self.__next_f.push([1,"{\"content\":['
    r'{\"id\":\"49725343\",\"legacyJobNo\":\"1\",\"title\":\"t\",'
    r'\"createdAt\":\"2026-08-06T10:13:04.91+09:00\",'
    r'\"applicationPeriod\":{\"start\":\"2026-08-05T00:00:00+09:00\",\"end\":\"2026-08-21T23:00:00+09:00\"},'
    r'\"_internal_keywordList\":[\"기업교육\",\"베트남어\"]},'
    r'{\"id\":\"49651217\",\"legacyJobNo\":\"2\",\"title\":\"t2\",'
    r'\"createdAt\":\"2026-07-25T07:03:10.437+09:00\",'
    r'\"applicationPeriod\":{\"start\":\"2026-07-25T00:00:00+09:00\",\"end\":\"2070-01-01T00:00:00+09:00\"},'
    r'\"_internal_keywordList\":[]}'
    r']}"]);</script></body>'
)

JOBKOREA_HTML_WITH_PAYLOAD = JOBKOREA_HTML.replace("</body>", _JOBKOREA_PAYLOAD)


def test_jobkorea_reads_dates_from_the_embedded_payload(fake_http):
    """The cards show no date; the JSON embedded in the same response does."""
    fake_http(FakeResponse(text=JOBKOREA_HTML_WITH_PAYLOAD))
    jobs = JobKoreaCollector().collect("베트남어")

    by_id = {job.source_job_id: job for job in jobs}
    first = by_id["49725343"]
    assert first.posted_at == datetime(2026, 8, 6, 10, 13, 4, 910000)
    assert first.deadline == datetime(2026, 8, 21, 23, 0)
    assert first.keywords == "기업교육,베트남어"


def test_jobkorea_treats_the_far_future_deadline_as_always_open(fake_http):
    """2070-01-01 is the 상시채용 sentinel, not a real deadline."""
    fake_http(FakeResponse(text=JOBKOREA_HTML_WITH_PAYLOAD))
    jobs = {job.source_job_id: job for job in JobKoreaCollector().collect("베트남어")}
    assert jobs["49651217"].deadline is None
    assert jobs["49651217"].posted_at is not None


def test_jobkorea_still_works_without_the_payload(fake_http):
    """Losing the JSON must cost dates only - never the results."""
    fake_http(FakeResponse(text=JOBKOREA_HTML))
    jobs = JobKoreaCollector().collect("베트남어")
    assert len(jobs) == 2
    assert all(job.posted_at is None for job in jobs)


def test_jobkorea_ignores_unrelated_content_arrays(fake_http):
    """Promo/region blocks also use "content"; only the job array has createdAt."""
    decoy = JOBKOREA_HTML.replace(
        "</body>",
        r"""<script>self.__next_f.push([1,"{\"content\":[{\"id\":\"78\",\"name\":\"지역채용관\"}]}"]);</script></body>""",
    )
    fake_http(FakeResponse(text=decoy))
    jobs = JobKoreaCollector().collect("베트남어")
    assert len(jobs) == 2
    assert all(job.posted_at is None for job in jobs)


def test_jobkorea_one_link_per_job_even_with_repeated_anchors(fake_http):
    fake_http(FakeResponse(text=JOBKOREA_HTML))
    jobs = JobKoreaCollector().collect("베트남어")
    assert len({job.source_job_id for job in jobs}) == len(jobs)


def test_jobkorea_returns_nothing_for_a_block_page(fake_http):
    fake_http(FakeResponse(text="<html><body>접근이 제한되었습니다</body></html>"))
    assert JobKoreaCollector().collect("베트남어") == []


def test_jobkorea_respects_the_limit(fake_http):
    fake_http(FakeResponse(text=JOBKOREA_HTML))
    assert len(JobKoreaCollector().collect("베트남어", limit=1)) == 1


# ------------------------------------------------------------------ incruit

INCRUIT_HTML = """
<html><body>
  <ul class="c_row">
    <li class="c_col">
      <div class="cell_first"><a href="/company/1234">(주)엔씨</a></div>
      <div class="cell_mid">
        <a href="https://job.incruit.com/jobdb_info/jobpost.asp?job=2607230000034&src=g">
          [단기계약직] 베트남어 번역 담당자 모집
        </a>
        <span>경기 성남시 신입 학력무관 계약직 통번역사 ~09.06 (일) (3일전 등록)</span>
      </div>
    </li>
  </ul>
</body></html>
"""


def test_incruit_parses_a_card(fake_http):
    fake_http(FakeResponse(text=INCRUIT_HTML))
    jobs = IncruitCollector().collect("베트남어")

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "incruit"
    assert job.source_job_id == "2607230000034"
    assert job.title == "[단기계약직] 베트남어 번역 담당자 모집"
    assert job.company == "(주)엔씨"
    assert job.location == "경기 성남시"
    assert job.location_region == "경기"
    assert job.employment_type == "계약직"
    assert job.experience == "신입"
    assert job.education == "학력무관"
    assert job.posted_at is not None      # "(3일전 등록)"
    assert job.deadline is not None       # "~09.06"
    assert job.url.startswith("https://job.incruit.com/jobdb_info/")


@pytest.mark.parametrize(
    "detail,today,expected",
    [
        ("~09.06 (일)", date(2026, 8, 8), datetime(2026, 9, 6, 23, 59)),
        # a December posting closing in January belongs to next year
        ("~01.15 (목)", date(2026, 12, 20), datetime(2027, 1, 15, 23, 59)),
        ("~08.08 (토)", date(2026, 8, 8), datetime(2026, 8, 8, 23, 59)),  # closes today
        ("상시채용", date(2026, 8, 8), None),
        ("~13.45", date(2026, 8, 8), None),  # nonsense date
    ],
)
def test_incruit_deadline_handles_year_rollover(detail, today, expected):
    assert IncruitCollector._deadline(detail, today=today) == expected


# ------------------------------------------------------------------ jobploy


def jobploy_card(slug: str, company: str, title: str, tags: list[str]) -> str:
    tag_html = "".join(f'<span class="tag">{tag}</span>' for tag in tags)
    return f"""
    <div class="item">
      <a class="item_link" href="https://www.jobploy.kr/ko/recruit/{slug}">
        <div class="top_line"><span class="text-info">{company}</span></div>
        <div class="recruit_title"><div class="title">{title}</div></div>
        <div class="tags">{tag_html}</div>
      </a>
    </div>
    """


JOBPLOY_HTML = (
    '<html><body><div class="content"><div class="recruit-list">'
    + jobploy_card(
        "welding-gyeongnam-dump",
        "진강용접",
        "덤프트럭 적재함 용접공 구합니다.",
        ["월급 : 2,500,000 원", "경상남도 함안군", "용접", "마감 D-4"],
    )
    + jobploy_card(
        "logistics-incheon-coupang",
        "쿠팡풀필먼트서비스",
        "쿠팡 물류센터 사원 모집",  # no keyword -> the site's default filler
        ["시급 : 10,500 원", "인천광역시 중구 외 + 4", "입, 출고/재고 관리", "마감 D-143"],
    )
    + "</div></div></body></html>"
)


def test_jobploy_parses_and_normalizes(fake_http):
    fake = fake_http(FakeResponse(text=JOBPLOY_HTML))
    jobs = JobployCollector().collect("용접")

    assert len(jobs) == 1  # the non-matching filler row was dropped
    job = jobs[0]
    assert job.source == "jobploy"
    assert job.source_job_id == "welding-gyeongnam-dump"
    assert job.title == "덤프트럭 적재함 용접공 구합니다."
    assert job.company == "진강용접"
    assert job.location == "경상남도 함안군"
    assert job.location_region == "경남"
    assert job.url == "https://www.jobploy.kr/ko/recruit/welding-gyeongnam-dump"
    assert job.deadline is not None

    # the site's search parameter is `search`; `query` is silently ignored
    _url, params = fake.calls[0]
    assert params == {"search": "용접"}


def test_jobploy_annualises_a_monthly_salary(fake_http):
    """월급 2,500,000원 is 3000만원 a year - not 250."""
    fake_http(FakeResponse(text=JOBPLOY_HTML))
    job = JobployCollector().collect("용접")[0]
    assert job.salary == "월급 : 2,500,000 원"
    assert job.salary_value == 3000


def test_jobploy_drops_the_default_feed_when_nothing_matches(fake_http):
    """A keyword with no hits must yield nothing, not 50 unrelated ads."""
    fake_http(FakeResponse(text=JOBPLOY_HTML))
    assert JobployCollector().collect("베트남어") == []


def test_jobploy_keeps_rows_matching_a_different_keyword(fake_http):
    fake_http(FakeResponse(text=JOBPLOY_HTML))
    jobs = JobployCollector().collect("물류센터")
    assert len(jobs) == 1
    assert jobs[0].company == "쿠팡풀필먼트서비스"
    assert jobs[0].salary_value == round(10500 * 209 * 12 / 10000)


def test_jobploy_deadline_counts_from_today():
    now = datetime(2026, 8, 9, 12, 0)
    assert JobployCollector._deadline("마감 D-4", now=now) == datetime(2026, 8, 13, 23, 59)
    assert JobployCollector._deadline("상시채용", now=now) is None


def test_kowork_is_a_documented_placeholder():
    collector = KoworkCollector()
    assert collector.is_available() is False
    assert "client-side" in collector.unavailable_reason
    assert collector.collect("베트남어") == []


@pytest.mark.parametrize("cls", [KWorkCollector, BuddiesKoreaCollector])
def test_client_rendered_sites_are_placeholders_with_a_reason(cls):
    """Sites whose listings never appear in the served HTML."""
    collector = cls()
    assert collector.is_available() is False
    assert collector.unavailable_status() == SourceStatus.UNAVAILABLE
    assert len(collector.unavailable_reason) > 40  # a real explanation, not a shrug
    assert collector.collect("베트남어") == []


# ------------------------------------------------------------------- work24

WORK24_XML = """<?xml version="1.0" encoding="UTF-8"?>
<wantedRoot>
  <wanted>
    <company>대한물류</company>
    <title>외국인 근로자 통역 담당</title>
    <region>인천 남동구</region>
    <sal>월급 280만원</sal>
    <empTpNm>계약직</empTpNm>
    <career>경력무관</career>
    <wantedAuthNo>K123456789</wantedAuthNo>
    <wantedInfoUrl>https://www.work24.go.kr/wk/a/b/1200/detail.do?wantedAuthNo=K123456789</wantedInfoUrl>
    <regDt>2026-08-05</regDt>
    <jobsCdKorNm>통역·번역</jobsCdKorNm>
  </wanted>
</wantedRoot>
"""


def test_work24_is_unavailable_without_an_api_key():
    collector = Work24Collector()
    assert collector.is_available() is False
    assert "WORK24_API_KEY" in collector.unavailable_reason


def test_work24_parses_xml(monkeypatch, fake_http):
    monkeypatch.setattr("app.collectors.work24.settings.work24_api_key", "test-key")
    fake_http(FakeResponse(text=WORK24_XML))

    jobs = Work24Collector().collect("통역")
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source_job_id == "K123456789"
    assert job.company == "대한물류"
    assert job.location_region == "인천"
    assert job.employment_type == "계약직"
    assert job.experience == "경력무관"
    assert job.salary_value == 280 * 12


# ------------------------------------------------------------------ registry


def test_placeholder_sources_are_unavailable_with_a_reason():
    collector = AlbamonCollector()
    assert collector.is_available() is False
    assert collector.unavailable_reason
    assert collector.collect("베트남어") == []


def test_registry_builds_every_collector():
    collectors = build_collectors()
    assert len(collectors) == len(COLLECTOR_CLASSES)
    assert {"saramin", "jobkorea", "wanted", "work24"} <= set(collectors)


def test_get_collector_by_name():
    assert isinstance(get_collector("saramin"), SaraminCollector)
    assert get_collector("nope") is None
