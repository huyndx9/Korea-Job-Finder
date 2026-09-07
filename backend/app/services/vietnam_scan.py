"""베트남 구직자 대상 채용공고 전체 스캔.

"인터넷 전체를 훑는다"는 것은 어떤 크롤러도 할 수 없습니다. 대신 이 모듈은
**동작하는 모든 수집기**를, 한국 기업이 베트남인을 채용할 때 실제로 쓰는
한국어 표현들로 한 번에 훑고, 각 공고가 정말 베트남/외국인 대상인지 점수를
매깁니다.

키워드는 세 갈래에서 뽑았습니다.

1. 언어·국적 표현 - '베트남어', '베트남 근로자'
2. 외국인 채용 표현 - '외국인 채용', '이주노동자'
3. **비자 코드** - 실제로 베트남인이 한국에서 일하는 법적 경로입니다.
   E-9(비전문취업, 고용허가제)가 베트남 근로자에게 가장 흔하고,
   F-2/F-4/F-5/F-6(거주·재외동포·영주·결혼이민), H-2(방문취업),
   D-2/D-10(유학·구직)이 뒤를 잇습니다. 공고 본문에 회사가 받아주는 비자를
   적어두는 경우가 많아, 언어 키워드만으로는 놓치는 공고를 여기서 건집니다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: 스캔에 사용하는 검색어. 수집기 × 키워드만큼 요청이 나가므로 무한정 늘리지
#: 않고, 실제로 결과가 다른 것만 남겼습니다.
SCAN_KEYWORDS: list[str] = [
    # 1. 언어 / 국적
    "베트남어",
    "베트남어 통역",
    "베트남 근로자",
    "베트남",
    # 2. 외국인 채용
    "외국인 채용",
    "외국인 근로자",
    "외국인 가능",
    "이주노동자",
    # 3. 비자 (베트남인이 한국에서 일하는 실제 경로)
    "E-9",
    "고용허가제",
    "E-7",
    "F-4",
    "F-2 비자",
    "H-2",
    "D-10",
    "비자 지원",
    # 4. 관련 직무
    "통번역",
    "다문화",
]

#: (정규식, 점수, 태그). 여러 개가 맞으면 합산하되 100점에서 자릅니다.
_SIGNALS: list[tuple[re.Pattern[str], int, str]] = [
    (re.compile(r"베트남어"), 45, "베트남어"),
    (re.compile(r"베트남"), 35, "베트남"),
    (re.compile(r"비엣남|비엣"), 25, "베트남"),
    (re.compile(r"외국인\s*(채용|근로자|가능|우대|전용|지원)"), 22, "외국인채용"),
    (re.compile(r"고용허가|\bEPS\b", re.I), 20, "고용허가제"),
    (re.compile(r"(?<![A-Za-z])E-?9(?![0-9])"), 20, "E-9"),
    (re.compile(r"(?<![A-Za-z])E-?7(?![0-9])"), 15, "E-7"),
    (re.compile(r"(?<![A-Za-z])F-?[2456](?![0-9])"), 15, "F비자"),
    (re.compile(r"(?<![A-Za-z])H-?2(?![0-9])"), 15, "H-2"),
    (re.compile(r"(?<![A-Za-z])D-?(2|10)(?![0-9])"), 12, "D비자"),
    (re.compile(r"비자\s*(지원|스폰서|발급|무관|가능)"), 15, "비자지원"),
    (re.compile(r"이주노동자|이주민|결혼이민|다문화"), 12, "다문화"),
    (re.compile(r"통번역|통역|번역"), 10, "통역"),
    (re.compile(r"TOPIK|한국어능력시험", re.I), 10, "한국어"),
    (re.compile(r"외국인"), 8, "외국인"),
]

MAX_SCORE = 100


@dataclass
class Relevance:
    score: int
    tags: list[str]

    @property
    def tag_text(self) -> str | None:
        return ",".join(self.tags) if self.tags else None


def score_text(*parts: str | None) -> Relevance:
    """공고 텍스트가 얼마나 '베트남/외국인 대상'인지 0-100 으로 매깁니다.

    검색어가 아니라 **공고 내용**을 보고 판단하므로, 일반 키워드로 걸려온
    공고도 실제로 외국인 채용이면 높은 점수를 받습니다.
    """
    blob = " ".join(p for p in parts if p)
    if not blob:
        return Relevance(0, [])

    total = 0
    tags: list[str] = []
    for pattern, weight, tag in _SIGNALS:
        if pattern.search(blob):
            total += weight
            if tag not in tags:
                tags.append(tag)
    return Relevance(min(total, MAX_SCORE), tags)
