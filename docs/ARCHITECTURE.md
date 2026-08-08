# VietJob Korea AI — Architecture

## 1. Tổng quan hệ thống

```
┌──────────────────────────────────────────────────────────────────┐
│                        apps/web  (React + Vite)                  │
│   Dashboard · Search · Job Detail · Matches · Resume · Alerts     │
└───────────────────────────────┬──────────────────────────────────┘
                                │ HTTP / JSON  (TanStack Query)
┌───────────────────────────────▼──────────────────────────────────┐
│                       apps/api  (FastAPI)                        │
│                                                                  │
│  api/         ← routers, dependencies, error handlers            │
│  schemas/     ← Pydantic request/response contracts              │
│  services/    ← business logic (không chứa SQL, không chứa HTTP) │
│  repositories/← truy cập DB (chỉ nơi này biết SQLAlchemy)        │
│  models/      ← SQLAlchemy ORM                                   │
│  sources/     ← JobSourceAdapter + registry + http client        │
│  pipeline/    ← normalize → dedupe → analyze → embed             │
│  ai/          ← AIProvider abstraction + prompts + validation    │
│  matching/    ← deterministic scoring engine                     │
│  search/      ← keyword + semantic + hybrid ranking              │
│  resume/      ← PDF/DOCX/TXT parsing                             │
│  workers/     ← TaskQueue abstraction + scheduled jobs           │
│  core/        ← config, logging, db engine, errors, security     │
└──────┬───────────────────────────────────────┬───────────────────┘
       │                                       │
┌──────▼──────────────┐              ┌─────────▼──────────────┐
│  Database           │              │  Task Queue            │
│  ─────────────────  │              │  ────────────────────  │
│  prod: PostgreSQL   │              │  prod: Celery + Redis  │
│        + pgvector   │              │  local: ThreadQueue    │
│  local: SQLite      │              │         (in-process)   │
│         + FTS5      │              │                        │
└─────────────────────┘              └────────────────────────┘
```

## 2. Nguyên tắc phân tầng

Luồng phụ thuộc **một chiều**, không có vòng lặp:

```
api  →  services  →  repositories  →  models  →  DB
          │
          ├→ ai/
          ├→ matching/
          ├→ search/
          └→ sources/
```

Quy tắc bắt buộc:

| Tầng | Được phép | Cấm |
|---|---|---|
| `api/` | gọi `services/`, dùng `schemas/` | viết SQL, gọi `repositories/` trực tiếp, gọi HTTP ra ngoài |
| `services/` | gọi `repositories/`, `ai/`, `matching/`, `search/` | import `fastapi`, biết về HTTP request |
| `repositories/` | SQLAlchemy, `models/` | business logic, gọi AI |
| `models/` | SQLAlchemy declarative | mọi thứ khác |
| `sources/` | httpx, parsing | ghi DB trực tiếp (trả `RawJob`, pipeline mới ghi) |

Lý do: cho phép test `services/` mà không cần HTTP server, test `repositories/` mà không cần business logic.

## 3. Data Pipeline

```
  Source Adapter                (sources/)
        │  RawJob
        ▼
  Normalizer                    (pipeline/normalize.py)
        │  NormalizedJob
        ▼
  Deduplicator  ── 4 tầng ──►   (pipeline/dedupe.py)
        │  L1 source+external_id
        │  L2 company+title+location (normalized)
        │  L3 content_hash
        │  L4 embedding cosine similarity
        ▼
  Persist  (jobs)               (repositories/job.py)
        │
        ▼
  AI Analyzer                   (ai/ + pipeline/analyze.py)
        │  JobAnalysis (Pydantic-validated)
        ▼
  Embedder                      (search/embedding.py)
        │  vector
        ▼
  Index  (FTS + vector)         (search/)
```

Mỗi bước ghi `PipelineRun` để admin dashboard đọc số liệu **thật**, không hard-code.

Nguyên tắc chịu lỗi: **một source chết không làm chết pipeline**. Mỗi source chạy trong `try/except` riêng, lỗi ghi vào `source_runs.error`, các source khác tiếp tục.

## 4. Database Strategy — Dual Dialect

Ứng dụng chạy trên 2 dialect. Sự khác biệt **chỉ tồn tại ở tầng repository/search**, không rò rỉ lên service.

| Tính năng | PostgreSQL (production) | SQLite (local) |
|---|---|---|
| Full-text search | `tsvector` + GIN index | FTS5 virtual table |
| Vector search | `pgvector` + HNSW index | float32 BLOB + brute-force cosine |
| JSON columns | `JSONB` | `JSON` (text) |
| Array columns | `ARRAY(TEXT)` | `JSON` list |
| UUID | native `uuid` | `CHAR(36)` |

Cơ chế: `core/db/types.py` định nghĩa các `TypeDecorator` chọn implementation theo dialect tại thời điểm compile. Model code viết một lần, chạy cả hai.

Giới hạn đã biết: brute-force cosine trên SQLite là O(n). Chấp nhận được ở chế độ single-user (dataset kỳ vọng < 100k jobs). Production dùng pgvector HNSW.

## 5. AI Provider Abstraction

```python
class AIProvider(Protocol):
    name: str
    async def complete_json(
        self, *, prompt: str, schema: type[BaseModel], timeout: float
    ) -> BaseModel: ...
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
```

Implementations: `AnthropicProvider`, `OpenAIProvider`, `GeminiProvider`, `LocalProvider`, `NullProvider`.

`NullProvider` **không fake kết quả** — nó raise `AIUnavailableError`, khiến job chuyển sang `AI_ANALYSIS_PENDING`. Đây là hành vi đúng khi chưa cấu hình API key, không phải fallback giả.

Chuỗi xử lý output LLM:
```
LLM raw text → extract JSON → Pydantic validate
   ├ hợp lệ  → lưu
   ├ malformed → retry (tối đa N lần, exponential backoff)
   └ hết retry → dead-letter + job.status = AI_ANALYSIS_PENDING
```

## 6. Matching Engine — Deterministic

Matching **không** gọi LLM để tính điểm. Điểm số tính bằng thuật toán xác định:

```
overall = Σ (dimension_score × weight)

skills       0.25
experience   0.20
language     0.15
visa         0.15
education    0.10
preferences  0.10
location     0.05
```

Lý do: cùng candidate + job phải luôn ra cùng một số. LLM không đảm bảo điều này.

LLM **chỉ** được dùng để diễn giải kết quả bằng ngôn ngữ tự nhiên (`explanation`), và phần diễn giải đó không được phép thay đổi con số.

Mỗi dimension trả về `DimensionScore { score, weight, strengths[], gaps[], evidence[] }` → explainability là dữ liệu có cấu trúc, không phải văn bản LLM sinh ra.

## 7. Search Ranking

```
final_score = w1 · keyword_relevance      (BM25 / ts_rank)
            + w2 · semantic_similarity    (cosine)
            + w3 · user_preference_boost
            + w4 · ai_match_score
            + w5 · recency_decay
```

Trọng số cấu hình được, mặc định trong `search/ranking.py`.

Nguyên tắc bắt buộc: **lọc và phân trang ở tầng database**, không bao giờ `SELECT *` rồi filter bằng Python.

## 8. Task Queue Abstraction

```python
class TaskQueue(Protocol):
    async def enqueue(self, task: str, **kwargs) -> str: ...
    async def status(self, task_id: str) -> TaskStatus: ...
```

| Backend | Dùng khi |
|---|---|
| `CeleryTaskQueue` | production, có Redis |
| `ThreadTaskQueue` | local dev, không có Redis — chạy worker in-process, state lưu ở bảng `task_runs` |

Cả hai đều ghi `task_runs` vào DB, nên admin dashboard hiển thị số liệu thật ở cả hai chế độ.

## 9. Single-User Mode (v1)

```python
async def get_current_user(...) -> User:
    if settings.single_user_mode:
        return await user_repo.get_local_owner()   # id cố định, seed lúc startup
    raise NotImplementedError("Auth chưa implement — xem Phase 15")
```

Toàn bộ tầng dưới vẫn nhận `user_id`. Khi bổ sung auth thật, chỉ thay thân hàm này.

Guard an toàn (fail-fast lúc startup):
- `APP_ENV=production` + `SINGLE_USER_MODE=true` → **refuse to start**
- Single-user mode → server chỉ bind `127.0.0.1`

## 10. Frontend

```
src/
├── components/     ui/ (shadcn primitives) + domain components
├── pages/          route components
├── layouts/        AppShell (sidebar + header)
├── hooks/          useJobs, useMatches, useProfile...
├── services/       API client (fetch wrapper + typed endpoints)
├── stores/         client state (filters, UI preferences)
├── types/          generated/shared types khớp với Pydantic schemas
└── utils/
```

- Server state: **TanStack Query** (cache, retry, invalidation).
- Client state: Zustand cho filter/UI, không lưu server data.
- Form: React Hook Form + Zod, schema Zod mirror Pydantic schema.
- Mọi list phải có: loading skeleton, empty state, error state.

## 11. Observability

Structured JSON logging (`structlog`). Mỗi crawler run ghi: `source`, `duration_ms`, `status`, `jobs_found`, `jobs_created`, `jobs_updated`, `duplicates`, `errors`.

Mỗi AI call ghi: `provider`, `model`, `tokens_in`, `tokens_out`, `duration_ms`, `success`.

**Không bao giờ log:** password, API key, access token, nội dung CV, thông tin cá nhân người dùng. Có filter ở tầng logging processor, không dựa vào kỷ luật của người viết code.

## 12. Thư mục dữ liệu local

```
data/
├── vietjob.db          SQLite database (gitignored)
├── resumes/            file CV upload (gitignored)
└── cache/              HTTP cache của crawler (gitignored)
```
