"""베트남/외국인 대상 공고 스캔: 점수 산정과 /api/scan."""

from __future__ import annotations

import pytest

from app.models import Job
from app.services.vietnam_scan import MAX_SCORE, SCAN_KEYWORDS, score_text
from tests.test_api import FakeCollector


# ------------------------------------------------------------------ 키워드 팩


def test_scan_keywords_cover_language_foreigner_and_visa():
    joined = " ".join(SCAN_KEYWORDS)
    assert "베트남어" in joined            # 언어
    assert "외국인" in joined              # 외국인 채용
    assert "E-9" in joined                 # 고용허가제 - 베트남 근로자 주 경로
    assert any(v in joined for v in ("F-4", "F-2", "H-2"))  # 거주/방문취업 비자
    assert len(SCAN_KEYWORDS) == len(set(SCAN_KEYWORDS)), "중복 키워드 없음"


# --------------------------------------------------------------------- 점수


@pytest.mark.parametrize(
    "title,description,expect_at_least,expect_tag",
    [
        ("베트남어 통역 담당자 모집", "통역 업무", 80, "베트남어"),
        ("외국인 근로자 채용", "E-9 비자 가능, 기숙사 제공", 50, "E-9"),
        ("생산직 사원 모집", "F-4 비자 소지자 우대", 10, "F비자"),
        ("주방보조", "외국인 지원 가능", 20, "외국인채용"),
        ("고용허가제 근로자 채용", "성실근로자", 20, "고용허가제"),
    ],
)
def test_score_recognises_vietnamese_and_visa_signals(title, description, expect_at_least, expect_tag):
    result = score_text(title, None, description, None)
    assert result.score >= expect_at_least
    assert expect_tag in result.tags


def test_unrelated_job_scores_zero():
    result = score_text("백엔드 개발자 채용", "네이버", "Python 경력 3년", None)
    assert result.score == 0
    assert result.tags == []


def test_score_is_capped():
    loud = "베트남어 베트남 외국인 채용 E-9 E-7 F-4 H-2 D-10 비자 지원 통역 TOPIK 다문화 고용허가"
    assert score_text(loud).score == MAX_SCORE


def test_visa_code_does_not_match_inside_other_words():
    """'E-9' 는 코드일 때만 잡아야 합니다 - 'LINE-95' 같은 문자열은 아님."""
    assert "E-9" not in score_text("MODEL LINE-95 운영").tags


def test_empty_text_is_zero():
    assert score_text(None, None).score == 0
    assert score_text("").score == 0


# ----------------------------------------------------------------- /api/scan


@pytest.fixture
def vietnam_collector(monkeypatch):
    """검색어와 무관하게 베트남/일반 공고를 섞어 돌려주는 수집기."""

    class Mixed(FakeCollector):
        rows = [
            ("베트남어 통역 담당자", "가나다회사", "서울 강남구", "서울", "정규직", "경력무관", 3500),
            ("외국인 근로자 채용 E-9", "라마바회사", "경기 화성시", "경기", "계약직", "신입", 3000),
            ("백엔드 개발자", "사아자회사", "부산 해운대구", "부산", "정규직", "경력", 5000),
        ]

    monkeypatch.setattr(
        "app.services.search_service.build_collectors", lambda *_a, **_k: {"saramin": Mixed()}
    )


def test_scan_returns_only_relevant_jobs(client, vietnam_collector):
    body = client.post("/api/scan", json={"sources": ["saramin"]}).json()

    assert body["keywords_used"] == SCAN_KEYWORDS
    assert body["total_collected"] == 3
    assert body["matched"] == 2  # 개발자 공고는 걸러짐
    titles = [job["title"] for job in body["jobs"]]
    assert "백엔드 개발자" not in titles


def test_scan_sorts_by_relevance(client, vietnam_collector):
    jobs = client.post("/api/scan", json={"sources": ["saramin"]}).json()["jobs"]
    scores = [job["vn_score"] for job in jobs]
    assert scores == sorted(scores, reverse=True)
    assert jobs[0]["title"] == "베트남어 통역 담당자"
    assert jobs[0]["vn_tags"]


def test_scan_min_score_filters_harder(client, vietnam_collector):
    strict = client.post("/api/scan", json={"sources": ["saramin"], "min_score": 80}).json()
    assert strict["matched"] == 1
    assert strict["jobs"][0]["title"] == "베트남어 통역 담당자"


def test_scan_min_score_zero_keeps_everything(client, vietnam_collector):
    body = client.post("/api/scan", json={"sources": ["saramin"], "min_score": 0}).json()
    assert body["matched"] == 3


def test_scan_stores_scores_in_the_database(client, db, vietnam_collector):
    client.post("/api/scan", json={"sources": ["saramin"]})
    rows = {row.title: row for row in db.query(Job).all()}
    assert rows["베트남어 통역 담당자"].vn_score >= 80
    assert rows["백엔드 개발자"].vn_score == 0


def test_jobs_endpoint_can_filter_and_sort_by_score(client, vietnam_collector):
    client.post("/api/scan", json={"sources": ["saramin"]})

    filtered = client.get("/api/jobs?min_vn_score=50&limit=50").json()
    assert filtered["pagination"]["total"] >= 1
    assert all(job["vn_score"] >= 50 for job in filtered["jobs"])

    ordered = client.get("/api/jobs?sort=vn_score&limit=50").json()["jobs"]
    scores = [job["vn_score"] for job in ordered]
    assert scores == sorted(scores, reverse=True)


def test_scan_paginates(client, vietnam_collector):
    body = client.post("/api/scan", json={"sources": ["saramin"], "min_score": 0, "limit": 2}).json()
    assert len(body["jobs"]) == 2
    assert body["pagination"]["total_pages"] == 2
