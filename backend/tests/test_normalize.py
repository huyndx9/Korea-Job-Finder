"""Normalization: the messy strings sites emit -> the values the UI filters on."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.normalize_service import (
    find_salary_text,
    normalize_employment_type,
    normalize_experience,
    normalize_region,
    parse_posted_at,
    parse_salary,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("서울 강남구", "서울"),
        ("서울특별시 서초구", "서울"),
        ("경기 화성시", "경기"),
        ("수원시 영통구", "경기"),
        ("인천 남동구", "인천"),
        ("부산광역시 해운대구", "부산"),
        ("대전 유성구", "대전"),
        ("전국", "전국"),
        ("충남 천안시", "충남"),
        ("해외 베트남 하노이", "해외"),
        ("", None),
        (None, None),
        ("재택근무", None),
    ],
)
def test_normalize_region(raw, expected):
    assert normalize_region(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("정규직", "정규직"),
        ("계약직", "계약직"),
        ("기간제 근로자", "계약직"),
        ("아르바이트", "아르바이트"),
        ("알바 모집", "아르바이트"),
        ("파트타임 계약직 모집", "아르바이트"),
        ("정규직 전환형 인턴", "인턴"),
        ("프리랜서", "프리랜서"),
        ("병역특례", None),
        (None, None),
    ],
)
def test_normalize_employment_type(raw, expected):
    assert normalize_employment_type(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("신입", "신입"),
        ("경력", "경력"),
        ("경력 3년 이상", "경력"),
        ("경력무관", "경력무관"),
        ("학력/경력 무관", "경력무관"),
        # 학력무관 is about education and says nothing about experience
        ("학력무관", None),
        ("신입 학력무관 계약직", "신입"),
        ("경력 5년 이상 학력무관", "경력"),
        ("신입·경력", "경력무관"),
        ("경력2년↑", "경력"),
        # "노무관리자" contains 무관 but says nothing about experience
        ("총무, HRD·HRM, 노무관리자 즉시 지원 경력10년↑", "경력"),
        ("노무관리자 모집", None),
        (None, None),
    ],
)
def test_normalize_experience(raw, expected):
    assert normalize_experience(raw) == expected


@pytest.mark.parametrize(
    "raw,expected_value",
    [
        ("연봉 3,500만원", 3500),
        ("3,500만원", 3500),
        ("연봉 1억", 10000),
        ("월급 250만원", 3000),
        ("시급 12,000원", round(12000 * 209 * 12 / 10000)),
        ("일급 150,000원", round(150000 * 22 * 12 / 10000)),
        ("회사내규에 따름", None),
        ("면접 후 결정", None),
        (None, None),
    ],
)
def test_parse_salary(raw, expected_value):
    text, value = parse_salary(raw)
    assert value == expected_value
    if raw:
        assert text == raw


def test_parse_salary_keeps_unparsable_text_for_display():
    text, value = parse_salary("회사내규에 따름")
    assert text == "회사내규에 따름"
    assert value is None


@pytest.mark.parametrize(
    "blob,expected",
    [
        ("서울 강남구 학원·어학원·교육원, 외국어강사 즉시 지원", None),  # 학원/지원 are not money
        ("파트타임 시급 12,500원 모집", "시급 12,500원"),
        ("연봉 3,500만원~", "연봉 3,500만원"),
        ("경력2년↑ 즉시 지원", None),
    ],
)
def test_find_salary_text_requires_digits(blob, expected):
    assert find_salary_text(blob) == expected


def test_parse_posted_at_relative_and_absolute():
    now = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)

    assert parse_posted_at("오늘", now=now).date() == now.date()
    assert parse_posted_at("어제", now=now).date() == (now - timedelta(days=1)).date()
    assert parse_posted_at("3일 전", now=now).date() == (now - timedelta(days=3)).date()
    assert parse_posted_at("2026-08-01", now=now).date() == datetime(2026, 8, 1).date()
    assert parse_posted_at("2026.08.01", now=now).date() == datetime(2026, 8, 1).date()
    assert parse_posted_at("2026-08-01T09:00:00+09:00", now=now) is not None
    assert parse_posted_at("", now=now) is None
    assert parse_posted_at(None, now=now) is None


def test_parse_posted_at_is_timezone_naive_for_sqlite():
    parsed = parse_posted_at("2026-08-01T09:00:00+09:00")
    assert parsed is not None and parsed.tzinfo is None


def test_dates_are_normalized_to_korean_local_time():
    """A Korean board's 등록일 must not slide back a day via UTC."""
    # 2026-08-08 02:00 KST is still 2026-08-07 17:00 UTC
    parsed = parse_posted_at("2026-08-08T02:00:00+09:00")
    assert parsed == datetime(2026, 8, 8, 2, 0)

    # the same instant given as a UTC offset must land on the same KST wall clock
    assert parse_posted_at("2026-08-07T17:00:00+00:00") == datetime(2026, 8, 8, 2, 0)

    # unix timestamps too: 1754620220 == 2025-08-08 11:30:20 KST
    assert parse_posted_at("1754620220") == datetime(2025, 8, 8, 11, 30, 20)
