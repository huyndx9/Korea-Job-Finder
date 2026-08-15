"""Turn messy, source-specific strings into the small set of values the UI filters on.

Every collector runs its fields through these helpers, so "서울 강남구", "서울특별시
강남구" and "서울시 강남" all end up in the same 서울 bucket.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------- 지역 (region)

REGIONS: list[str] = [
    "서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종",
    "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주", "해외", "전국",
]

# longest / most specific spellings first
_REGION_PATTERNS: list[tuple[str, str]] = [
    ("서울", r"서울"),
    ("경기", r"경기|수원|성남|용인|고양|부천|안양|안산|화성|평택|시흥|파주|김포|광명|군포|하남|의정부|남양주"),
    ("인천", r"인천"),
    ("부산", r"부산"),
    ("대구", r"대구"),
    ("광주", r"광주광역시|광주시|광주"),
    ("대전", r"대전"),
    ("울산", r"울산"),
    ("세종", r"세종"),
    ("강원", r"강원|춘천|원주|강릉"),
    ("충북", r"충청북도|충북|청주|충주"),
    ("충남", r"충청남도|충남|천안|아산|서산|당진"),
    ("전북", r"전라북도|전북|전주|익산|군산"),
    ("전남", r"전라남도|전남|여수|순천|목포"),
    ("경북", r"경상북도|경북|포항|구미|경주|안동"),
    ("경남", r"경상남도|경남|창원|김해|양산|진주|거제"),
    ("제주", r"제주"),
    ("해외", r"해외|베트남|일본|중국|미국"),
    ("전국", r"전국"),
]


def normalize_region(location: str | None) -> str | None:
    """Map a free-form location string onto one 시/도 bucket."""
    if not location:
        return None
    text = location.strip()
    for region, pattern in _REGION_PATTERNS:
        if re.search(pattern, text):
            return region
    return None


# ------------------------------------------------------------ 고용형태 (type)

EMPLOYMENT_TYPES: list[str] = ["정규직", "계약직", "아르바이트", "인턴", "프리랜서"]

# checked in order - "인턴" before "정규직" so "정규직 전환형 인턴" lands on 인턴
_EMPLOYMENT_PATTERNS: list[tuple[str, str]] = [
    ("인턴", r"인턴|intern|체험형"),
    ("아르바이트", r"아르바이트|알바|파트타임|시간제|part[\s-]?time"),
    ("프리랜서", r"프리랜서|freelanc"),
    ("계약직", r"계약직|기간제|파견직|파견|위촉직|contract"),
    ("정규직", r"정규직|정규|상용직|full[\s-]?time"),
]


def normalize_employment_type(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip().lower()
    for label, pattern in _EMPLOYMENT_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return label
    return None


# --------------------------------------------------------------- 경력 (exp)

EXPERIENCE_LEVELS: list[str] = ["신입", "경력", "경력무관"]


def normalize_experience(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()

    # "학력무관" is about EDUCATION, not experience - a card reading
    # "신입 학력무관" is an entry-level job, not an experience-agnostic one.
    # Drop it before looking for an experience-related 무관.
    text = re.sub(r"학력\s*[/·]?\s*무관", " ", text)

    # "경력무관", "학력/경력 무관", "신입·경력" all mean: anyone can apply.
    # 무관 must be qualified - job titles like "노무관리자" contain it by accident.
    if re.search(r"(?:경력|연령|성별|전공|나이|자격)\s*[/·]?\s*무관", text):
        return "경력무관"
    if text.strip() in {"무관", "전체", "any", "Any"}:
        return "경력무관"
    has_new = bool(re.search(r"신입|entry", text, flags=re.IGNORECASE))
    has_exp = bool(re.search(r"경력|\d+\s*년|experienced?", text, flags=re.IGNORECASE))
    if has_new and has_exp:
        return "경력무관"
    if has_new:
        return "신입"
    if has_exp:
        return "경력"
    return None


# ------------------------------------------------------------- 급여 (salary)

# hours/days per month used to annualise 시급 / 일급 (Korean statutory 209h month)
_HOURS_PER_MONTH = 209
_DAYS_PER_MONTH = 22

_PERIOD_TO_ANNUAL: list[tuple[str, float]] = [
    (r"시급|시간당|hourly", _HOURS_PER_MONTH * 12),
    (r"일급|일당|daily", _DAYS_PER_MONTH * 12),
    (r"주급|weekly", 52),
    (r"월급|월\s*급|월\s*[\d,]|monthly", 12),
    (r"연봉|연\s*봉|annual|년봉", 1),
]

_NUMBER = r"(\d[\d,]*(?:\.\d+)?)"

# a money expression must carry digits - otherwise words like 학원 / 지원 / 교육원
# look like salaries to a naive "원 in text" check
_SALARY_EXPR = re.compile(
    r"(?:연봉|월급여|월급|시급|일급|주급|시간당|일당|월)?\s*"
    + _NUMBER
    + r"\s*(?:억|만\s*원?|원)"
)


def find_salary_text(text: str | None) -> str | None:
    """Pull the first money-looking phrase out of a blob of listing text."""
    if not text:
        return None
    match = _SALARY_EXPR.search(text)
    return match.group(0).strip() if match else None


def parse_salary(value: str | None) -> tuple[str | None, int | None]:
    """Return ``(display_text, annual_value_in_만원)``.

    The numeric value is a rough, sort-only estimate. Anything we cannot read
    ("회사내규에 따름", "면접 후 결정") keeps its text and gets a None value so it
    simply sinks to the bottom of a salary sort.
    """
    if not value:
        return None, None
    text = " ".join(str(value).split())
    if not text:
        return None, None

    # how often is it paid?
    factor = 1.0
    for pattern, mult in _PERIOD_TO_ANNUAL:
        if re.search(pattern, text, flags=re.IGNORECASE):
            factor = mult
            break

    amount_manwon: float | None = None
    if m := re.search(_NUMBER + r"\s*억", text):
        amount_manwon = float(m.group(1).replace(",", "")) * 10_000
    elif m := re.search(_NUMBER + r"\s*만\s*원?", text):
        amount_manwon = float(m.group(1).replace(",", ""))
    elif m := re.search(_NUMBER + r"\s*원", text):
        amount_manwon = float(m.group(1).replace(",", "")) / 10_000

    if amount_manwon is None:
        return text, None
    annual = int(round(amount_manwon * factor))
    # guard against parsing nonsense out of marketing copy
    if annual <= 0 or annual > 1_000_000:
        return text, None
    return text, annual


# ---------------------------------------------------------------- 날짜 (date)

#: Every source here is a Korean job board and every date the user sees is a
#: Korean one, so all timestamps are normalized to KST before the timezone is
#: dropped for SQLite. Storing UTC instead would show 2026-08-07 for a posting
#: made at 2026-08-08 02:00 KST. Korea has no DST, so a fixed +09:00 is exact.
KST = timezone(timedelta(hours=9))

_REL_DAYS = re.compile(r"(\d+)\s*일\s*전")
_DATE_PATTERNS = [
    (re.compile(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})"), ("y", "m", "d")),
    (re.compile(r"(\d{1,2})[-./](\d{1,2})(?!\d)"), ("m", "d")),
]


def to_kst_naive(value: datetime) -> datetime:
    """Convert an aware datetime to KST and drop the tzinfo for storage."""
    if value.tzinfo is None:
        return value
    return value.astimezone(KST).replace(tzinfo=None)


#: Sites encode "상시채용" (always open) as an absurd far-future date -
#: JobKorea uses 2070-01-01. Anything past this horizon is a sentinel, not a date.
_DEADLINE_HORIZON_DAYS = 365 * 5


def parse_deadline(value: object, now: datetime | None = None) -> datetime | None:
    """Like parse_posted_at, but discards 'always open' sentinel dates."""
    parsed = parse_posted_at(value, now=now)
    if parsed is None:
        return None
    reference = (now or datetime.now(KST)).astimezone(KST).replace(tzinfo=None)
    if parsed > reference + timedelta(days=_DEADLINE_HORIZON_DAYS):
        return None
    return parsed


def parse_posted_at(value: object, now: datetime | None = None) -> datetime | None:
    """Best-effort parse of the many date shapes Korean job boards emit.

    Always returns a naive datetime **in Korean local time**.
    """
    if value is None or value == "":
        return None
    now = (now or datetime.now(timezone.utc)).astimezone(KST)

    if isinstance(value, datetime):
        return to_kst_naive(value)

    # unix timestamp (seconds or milliseconds)
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit() and len(value) >= 10):
        try:
            ts = float(value)
            if ts > 1e11:  # milliseconds
                ts /= 1000
            return datetime.fromtimestamp(ts, tz=KST).replace(tzinfo=None)
        except (ValueError, OSError, OverflowError):
            return None

    text = str(value).strip()
    if not text:
        return None

    if "오늘" in text or "today" in text.lower() or "방금" in text:
        return now.replace(tzinfo=None)
    if "어제" in text:
        return (now - timedelta(days=1)).replace(tzinfo=None)
    if m := _REL_DAYS.search(text):
        return (now - timedelta(days=int(m.group(1)))).replace(tzinfo=None)

    # ISO-8601 first (wanted / most JSON APIs)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return to_kst_naive(parsed)
    except ValueError:
        pass

    for pattern, groups in _DATE_PATTERNS:
        if m := pattern.search(text):
            parts = dict(zip(groups, (int(g) for g in m.groups())))
            year = parts.get("y", now.year)
            try:
                return datetime(year, parts["m"], parts["d"])
            except ValueError:
                return None
    return None
