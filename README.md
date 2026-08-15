# 🇰🇷 Korea Job Finder

> 여러 한국 채용 사이트를 한 번에 검색하는 채용정보 통합검색 서비스
> — 외국인 구직자를 위해 만들었습니다.

키워드 하나를 입력하면 여러 채용 사이트를 **동시에** 조회하고, 데이터를 같은 기준으로
표준화하고, 중복 공고를 제거해 한 화면에 보여줍니다.

```
검색어: 베트남어  →  70여 건   |   외국인  →  100여 건   (약 2초, API 키 없이)
```

| | |
|---|---|
| **백엔드** | Python 3.11+ · FastAPI · SQLAlchemy · SQLite |
| **프론트엔드** | React 18 · Vite · Tailwind CSS · lucide-react |
| **수집** | httpx · BeautifulSoup (JS 렌더링 불필요) |
| **테스트** | pytest — 216개, 네트워크 호출 없음 |

---

## 목차

1. [주요 기능](#1-주요-기능)
2. [빠른 시작](#2-빠른-시작)
3. [수집 대상 사이트](#3-수집-대상-사이트)
4. [사이트 직접 추가](#4-사이트-직접-추가)
5. [설정](#5-설정)
6. [아키텍처](#6-아키텍처)
7. [API](#7-api)
8. [테스트](#8-테스트)
9. [알려진 한계](#9-알려진-한계)

---

## 1. 주요 기능

- **동시 검색** — 각 사이트를 별도 스레드에서 병렬 조회. 한 곳이 죽어도 나머지는 정상 반환
- **표준화** — 지역·고용형태·경력·급여·날짜를 사이트마다 다른 표기에서 하나의 기준으로 통일
- **중복 제거** — 같은 공고가 여러 사이트에 올라와도 한 번만 표시
- **정직한 상태 표시** — 실패한 소스는 이유를 그대로 노출 (`invalid_key`, `rate_limited` 등).
  실제 데이터를 샘플 데이터로 조용히 바꿔치기하지 않습니다
- **사이트 직접 추가** — 코드 수정 없이 UI에서 새 채용 사이트를 등록
- **필터·정렬·페이지네이션** — 전부 서버에서 처리
- **마감 임박 표시** — `D-3`, `오늘 마감`, `상시채용`

---

## 2. 빠른 시작

### 사전 준비

**Python 3.11+** 와 **Node 18+** 가 필요합니다.

```bash
# 백엔드
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
.venv/bin/python -m pip install -r requirements.txt           # macOS / Linux

# 프론트엔드
cd ../frontend
npm install
```

### 실행

**Windows** — `start.bat` 더블클릭 (서버 2개가 각각 별도 창에서 실행됩니다)

**터미널 (Git Bash / macOS / Linux)**

```bash
./start.sh
```

브라우저가 자동으로 http://localhost:5173 을 엽니다.

| 스크립트 | 역할 |
|---|---|
| `start.bat` / `start.sh` | 백엔드 + 프론트엔드 + 브라우저 |
| `run-backend.bat` / `run-backend.sh` | 백엔드만 (8000) |
| `run-frontend.bat` / `run-frontend.sh` | 프론트엔드만 (5173) |
| `stop.sh` | 8000 / 5173 포트를 쓰는 서버 강제 종료 |

**API 키는 하나도 필요 없습니다.** 잡코리아 · 인크루트 · 잡플로이 · 원티드 4개 사이트가
설정 없이 바로 동작합니다. 데이터베이스도 첫 실행 시 자동 생성됩니다.

### 문제 해결

| 증상 | 원인과 해결 |
|---|---|
| 채용 사이트 목록이 비어 있음 | 백엔드가 실행 중이 아닙니다. http://127.0.0.1:8000/api/health 확인 후 `run-backend` 실행. 백엔드가 살아나면 화면은 5초마다 자동 재시도합니다 |
| `포트가 이미 사용 중입니다` | `./stop.sh` 실행 (또는 열려 있는 서버 창을 닫기) |
| Git Bash에서 Ctrl+C 후에도 서버가 살아 있음 | MSYS2의 시그널 전달 한계입니다. `./stop.sh` 로 확실히 종료하세요 |

---

## 3. 수집 대상 사이트

### 바로 동작 (키 불필요)

| 사이트 | 방식 |
|---|---|
| **잡코리아** | 공개 검색 페이지. 등록일·마감일은 같은 응답에 포함된 JSON에서 추출 (추가 요청 없음) |
| **인크루트** | 공개 검색 페이지 (EUC-KR), `ul.c_row` 카드 |
| **잡플로이** | **외국인 채용 전문.** 서버 렌더링 검색 페이지 |
| **원티드** | 사이트가 사용하는 공개 JSON 엔드포인트 |
| 점핏 | 공개 JSON 엔드포인트 — IT 직군, 기본 선택 아님 |

### 키 필요

| 사이트 | 발급처 |
|---|---|
| **사람인** | https://oapi.saramin.co.kr — 개인도 즉시 발급. **키만 넣으면 코드 수정 없이 동작** |
| **워크24 (고용24)** | [WORK24-API-GUIDE.md](WORK24-API-GUIDE.md) 참고. ⚠️ 개인회원은 이 앱에 필요한 `채용정보목록` API를 받을 수 없습니다 |

### 수집 불가 (인터페이스만 구현)

알바몬 · 알바천국 · 인디드 · 커리어 · 잡플래닛 · 로켓펀치 · 코워크 · K-Work · 버디즈코리아

모두 클라이언트 렌더링이거나 봇 차단, 또는 공개 API가 없습니다. `/api/sources` 에 **사유가
그대로 표시**되며 검색을 방해하지 않습니다. 사유는 전부 실제 요청으로 확인한 결과입니다.

> **수집 원칙:** 로그인, 캡차 우회, 안티봇 회피, 레이트 리밋 무력화를 하지 않습니다.
> 평범한 공개 HTTP 요청으로 읽을 수 없는 사이트는 `unavailable` 로 표시합니다.

### 잡플로이 — 알아둘 특성

검색 결과가 없을 때 빈 목록 대신 **기본 목록(대부분 광고)** 을 반환합니다. 실측:

| 검색어 | 반환 | 실제로 검색어를 포함 |
|---|---:|---:|
| `용접` | 36 | 32 |
| `통역` | 34 | 4 |
| `베트남어` | 50 | **0** |

그대로 쓰면 무관한 공고 50건이 섞이므로 수집기가 다시 필터링합니다.
`베트남어` 로 잡플로이 결과가 0건인 것은 **정상**입니다. (검색 파라미터는 `search`.
`query` 는 받아들여지지만 무시됩니다.)

---

## 4. 사이트 직접 추가

**채용 사이트** 영역의 **➕ 사이트 추가** → 양식 입력 → **테스트** 로 결과 미리보기 →
**저장**. 코드 수정이 전혀 없고, 저장 즉시 검색·필터·중복 제거가 기존 소스와 동일하게
동작합니다.

| 항목 | 설명 |
|---|---|
| 검색 URL | **`{keyword}` 필수** — 예: `https://site.com/jobs?q={keyword}` |
| 유형 | `HTML` (CSS 선택자) 또는 `JSON` (`result.positions` 형태의 경로) |
| 공고 선택자 | 공고 **하나**를 감싸는 요소 |
| 제목 / 링크 선택자 | 필수 — 읽지 못하면 해당 공고는 건너뜁니다 |
| 회사 / 지역 / 급여 / 등록일 / 설명 | 선택 — 비우면 본문에서 추측 |

**예시 채우기** 버튼을 누르면 실제로 동작하는 설정(인크루트)이 입력됩니다.

> **보안:** 백엔드가 입력받은 URL을 직접 호출하므로 SSRF를 막습니다.
> `localhost`, `127.0.0.1`, 사설 IP 대역, `169.254.169.254`(클라우드 메타데이터),
> `http/https` 이외의 스킴은 모두 거부됩니다.

---

## 5. 설정

```bash
cp backend/.env.example backend/.env
```

| 변수 | 기본값 | 설명 |
|---|---|---|
| `SARAMIN_API_KEY` | (없음) | 사람인 Open API 키 |
| `WORK24_API_KEY` | (없음) | 고용24 Open API 키 |
| `DEMO_MODE` | `false` | `true` 일 때만 실패한 소스를 샘플 데이터로 대체 |
| `DATABASE_URL` | `sqlite:///korea_jobs.db` | 자동 생성 |
| `COLLECTOR_TIMEOUT` | `20` | 수집기별 타임아웃(초) |

### DEMO_MODE 에 대하여

기본값 `false` 에서는 **실제 데이터가 조용히 대체되는 일이 없습니다.** 키가 없거나 실패한
소스는 정확한 사유를 보고하고 0건을 반환합니다.

`true` 로 켠 경우에만 샘플 데이터가 사용되며, 그때도 항상 명확히 표시됩니다 —
API의 `is_mock=true`, 카드의 노란 **DEMO** 배지, 모든 정렬에서 실제 공고보다 아래 배치,
그리고 "원문 보기"는 해당 사이트의 실제 검색 페이지로 연결됩니다.

---

## 6. 아키텍처

```
POST /api/search {keywords, sources}
        ↓
수집기별 병렬 실행 (스레드 + 개별 타임아웃)
        ↓
표준화 → 검증 → 중복 제거 → SQLite 저장 (fingerprint 기준 upsert)
        ↓
사이트별 상태 · 소요 시간 · 제거된 중복 수 반환
        ↓
프론트엔드는 GET /api/jobs 로 목록 조회 (필터·정렬·페이지 모두 서버 처리)
```

```
backend/app/
├── main.py              FastAPI 앱, 시작 시 DB 생성
├── config.py            설정 (.env, 시크릿 하드코딩 없음)
├── models/              jobs · custom_sources 테이블
├── api/                 HTTP 엔드포인트
├── collectors/
│   ├── base.py          JobCollector 인터페이스
│   ├── saramin.py  jobkorea.py  wanted.py  work24.py
│   ├── incruit.py  jobploy.py   jumpit.py
│   ├── custom.py        사용자가 등록한 사이트 (설정 기반)
│   ├── placeholders.py  수집 불가 사이트 (사유 명시)
│   └── __init__.py      레지스트리 — 새 사이트는 여기에 등록
└── services/
    ├── search_service.py     병렬 수집 · 저장
    ├── normalize_service.py  지역/고용형태/경력/급여/날짜
    ├── dedup_service.py      fingerprint
    └── job_query.py          필터 · 정렬 · 페이지네이션
```

### 데이터 모델

모든 공고가 하나의 스키마로 표준화됩니다. 주요 컬럼:

| 컬럼 | 설명 |
|---|---|
| `source`, `source_job_id` | 출처와 원본 ID |
| `location_region` | 표준화된 시/도 (필터용) |
| `salary`, `salary_value` | 원문 + 정렬용 연봉 환산값(만원) |
| `employment_type`, `experience` | 정규직/계약직/아르바이트/인턴/프리랜서 · 신입/경력/경력무관 |
| `posted_at`, `deadline` | **한국 시간(KST)**. `deadline` 이 비면 상시채용 |
| `fingerprint` | UNIQUE — 중복 제거 키 |
| `is_mock` | `1` = 샘플 데이터 |

모든 시각은 저장 전에 **KST(UTC+9)** 로 변환합니다. UTC로 저장하면 한국 새벽 2시 공고가
하루 전날로 표시됩니다.

**중복 제거**는 ① `source + source_job_id`, ② 없으면 `company + title + location`
(공백·기호·`주식회사`/`㈜` 제거) 기준입니다. 둘 다 하나의 `fingerprint` 로 요약되며
UNIQUE 인덱스가 재검색 시 중복 누적을 막습니다.

### 새 사이트를 코드로 추가

```python
from app.collectors.base import JobCollector, NormalizedJob

class MySiteCollector(JobCollector):
    name = "mysite"
    label = "마이사이트"
    site_url = "https://example.com"

    def search(self, keyword: str, limit: int = 50, **_options) -> list[dict]:
        with self._client() as client:           # httpx, 타임아웃·UA 설정됨
            response = client.get(URL, params={"q": keyword})
            response.raise_for_status()
            return response.json()["items"]

    def normalize(self, raw_job: dict) -> NormalizedJob | None:
        return NormalizedJob(
            source=self.name,
            source_job_id=str(raw_job["id"]),
            title=raw_job["title"],
            company=raw_job["company"],
            url=raw_job["url"],
        )
```

`app/collectors/__init__.py` 의 `COLLECTOR_CLASSES` 에 추가하면 끝입니다.
`/api/sources`, 소스 필터, 병렬 검색이 자동으로 인식합니다.

---

## 7. API

| 엔드포인트 | 설명 |
|---|---|
| `GET /api/health` | 앱·DB 상태, 저장된 공고 수 |
| `GET /api/sources` | 소스별 상태 (key = 소스 이름) |
| `POST /api/search` | 사이트에서 수집 후 저장 |
| `GET /api/jobs` | 저장된 공고 조회 (필터·정렬·페이지) |
| `GET /api/jobs/{id}` | 공고 상세 |
| `GET·POST·PATCH·DELETE /api/sources/custom` | 직접 추가한 소스 관리 |
| `POST /api/sources/custom/test` | 시험 실행 — 저장하지 않음 |

자동 생성 문서: http://127.0.0.1:8000/docs

```bash
curl -X POST http://127.0.0.1:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"keywords":["베트남어"],"sources":["jobkorea","incruit","jobploy","wanted"]}'
```

`GET /api/jobs` 파라미터: `keyword`(반복 가능, OR), `source`, `location`,
`employment_type`, `experience`(모두 반복 가능), `sort`
(`latest`·`oldest`·`salary_desc`·`salary_asc`), `page`, `limit`(최대 100).

소스 상태값: `connected`, `idle`, `not_configured`, `invalid_key`, `invalid_request`,
`rate_limited`, `api_error`, `error`, `timeout`, `unavailable`, `demo`.

---

## 8. 테스트

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q      # Windows
.venv/bin/python -m pytest -q              # macOS / Linux
```

**216개 테스트. 실제 네트워크를 호출하는 테스트는 하나도 없으며, 저장소에 실제 API 키는
존재하지 않습니다.** 수집기는 항상 가짜 응답으로 대체됩니다.

범위: 한국어 표준화 · 중복 제거 · 수집기별 HTML/JSON/XML 파싱 · API(필터·정렬·페이지) ·
오류 처리(수집기 크래시, 타임아웃, 키 없음/오류, 한도 초과, 깨진 데이터 행, 동시 쓰기 충돌) ·
SSRF 차단.

---

## 9. 알려진 한계

- **원티드**는 목록에 급여·등록일을 주지 않아 해당 필드가 비어 있습니다.
- 일부 공고에 등록일이 없습니다(`베트남어` 기준 약 13%). 이런 공고는 날짜 정렬에서 항상
  맨 아래로 밀리며 위로 올라오지 않습니다.
- 잡코리아·인크루트의 HTML은 언제든 바뀔 수 있습니다. 파서는 CSS 클래스가 아니라 공개 링크
  구조에 의존해 비교적 견고하지만, 대규모 개편 시 해당 소스는 0건을 반환합니다
  (오류로 보고되며 앱은 죽지 않습니다).
- `salary_value` 는 정렬용 **추정치**입니다 (시급 × 209시간 × 12). 공식 수치가 아닙니다.
- 키워드 검색은 `LIKE` 기반이며 아직 full-text search가 아닙니다.
- 새로 추가한 소스는 페이지를 새로고침해야 목록에 나타납니다.
- 워크24 수집기의 엔드포인트는 고용24 개편 이전 주소라 현재 404입니다. 인증키 발급 후
  활용가이드의 새 주소로 수정이 필요합니다 ([상세](WORK24-API-GUIDE.md)).

---

## 면책

이 프로젝트는 각 채용 사이트의 **공개 정보를 검색해 링크로 연결**할 뿐이며, 공고 원문의
권리는 각 채용 사이트와 게시 기업에 있습니다. 실제 지원은 원본 사이트에서 이루어집니다.
수집한 데이터를 재판매하지 않습니다.
