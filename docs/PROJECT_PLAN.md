# VietJob Korea AI — Project Plan

> Nền tảng tổng hợp việc làm + AI matching cho người Việt tìm việc tại Hàn Quốc.

Tài liệu này là **kế hoạch thi công**. Kiến trúc chi tiết xem [ARCHITECTURE.md](ARCHITECTURE.md).
Các quyết định kỹ thuật và lý do xem [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md).

---

## 1. Phase 0 — Audit Result

### 1.1 Repository

Thư mục làm việc `C:\Claude code\TÌm việc` **trống hoàn toàn**, chỉ chứa `.claude/settings.local.json`.

- Không có `package.json`, `requirements.txt`, `README.md`, database schema, hay source code.
- Không phải git repository (đã `git init` trong Phase 0).

→ **Greenfield project.** Không có code cũ cần bảo toàn, không có architecture cũ để tôn trọng.

### 1.2 Môi trường thực thi

| Thành phần | Trạng thái | Ghi chú |
|---|---|---|
| OS | Windows 10 Pro 19045 | Shell chính: PowerShell 5.1 |
| Node.js | v24.18.0 | ✅ |
| npm | 11.16.0 | ✅ |
| Python | 3.14.6 (duy nhất) | ✅ |
| Git | 2.55.0 | ✅ |
| **Docker / Docker Compose** | ❌ **không cài đặt** | Ràng buộc lớn nhất |
| **PostgreSQL** | ❌ không có service, không có `psql` | |
| **Redis** | ❌ không có service, không có `redis-cli` | |
| pnpm / uv | ❌ | Dùng npm + pip |

### 1.3 Kiểm chứng dependency trên Python 3.14

Python 3.14 rất mới nên rủi ro thiếu wheel là có thật. **Đã cài thử thực tế** trong venv, kết quả:

✅ Tất cả đều cài thành công:
`fastapi 0.141.1`, `pydantic 2.13.4`, `sqlalchemy 2.0.51`, `alembic 1.19.0`, `uvicorn`, `httpx`,
`psycopg[binary,pool]`, `asyncpg`, `pgvector`, `redis`, `celery`, `aiosqlite`, `fakeredis`,
`pytest`, `pytest-asyncio`, `ruff`, `mypy`, `bcrypt`, `pyjwt`, `beautifulsoup4`, `lxml`,
`pypdf`, `python-docx`, `structlog`, `tenacity`, `anthropic`, `openai`, `google-genai`.

→ Không cần hạ version Python. Không có dependency conflict.

### 1.4 Ràng buộc phát sinh từ audit

| # | Ràng buộc | Hệ quả kiến trúc |
|---|---|---|
| C1 | Không có Docker | Local dev **phải chạy được không cần container**. `docker-compose.yml` vẫn viết cho production/deploy nhưng không phải đường chạy mặc định. |
| C2 | Không có PostgreSQL | DB layer phải **dual-dialect**: SQLite (local) + PostgreSQL/pgvector (production). Xem ADR-002. |
| C3 | Không có Redis | Task queue phải có backend thay thế chạy in-process. Xem ADR-003. |
| C4 | Đường dẫn chứa ký tự non-ASCII (`TÌm việc`) và khoảng trắng | Mọi script phải quote path. Tránh tooling nhạy cảm với Unicode path. |
| C5 | Shell là PowerShell, không phải bash | `Makefile` không chạy được native (không có `make`). Cần script runner thay thế. Xem ADR-004. |

---

## 2. Thay đổi phạm vi theo yêu cầu người dùng

> "tôi muốn dùng app để bản thân sử dụng trước nên chưa cần tính năng đăng nhập"

**Quyết định:** chuyển sang **Single-User Local Mode** cho v1.

| Ban đầu | Điều chỉnh |
|---|---|
| Register / Login / JWT / refresh token | **Bỏ khỏi v1** |
| `users.password_hash` | Cột giữ nullable, không dùng ở v1 |
| `POST /api/auth/*` | Không implement ở v1 |
| Mọi endpoint đòi `Depends(get_current_user)` | Vẫn dùng `Depends(get_current_user)`, nhưng implementation trả về **local owner user** (id cố định, seed khi khởi động) |

**Lý do giữ nguyên dependency `get_current_user`:** toàn bộ tầng service/repository vẫn nhận `user_id`, nên khi bổ sung auth thật ở v2 chỉ cần thay thân hàm dependency — **không phải sửa business logic**. Đây là cách rẻ nhất để hoãn auth mà không tạo nợ kỹ thuật.

**Ràng buộc an toàn:** vì không có auth, API **chỉ bind `127.0.0.1`** ở chế độ local và có biến `APP_SINGLE_USER_MODE=true`. Nếu `APP_ENV=production` mà `APP_SINGLE_USER_MODE=true` → app **từ chối khởi động**. Xem ADR-005.

---

## 3. Phase Roadmap (đã điều chỉnh)

Mỗi phase chỉ được đóng khi qua **Quality Gate** của nó.

| Phase | Nội dung | Trạng thái |
|---|---|---|
| 0 | Audit + Docs | ✅ Done |
| 1 | Foundation: monorepo, backend skeleton, DB engine, frontend skeleton, tooling, test harness | ✅ Done |
| 2 | Local Profile (thay cho Auth): profile, skills, preferences | ⏳ |
| 3 | Job data model: companies, sources, jobs, saved_jobs, migrations, indexes | ⏳ |
| 4 | Job Source System: `JobSourceAdapter`, registry, rate limit, retry, circuit breaker, scheduler | ⏳ |
| 5 | Normalization + Deduplication (4 tầng) | ⏳ |
| 6 | AI Job Analysis: `AIProvider` abstraction, structured output, validation, fallback | ⏳ |
| 7 | Search: full-text + semantic + hybrid ranking + filters | ⏳ |
| 8 | Matching Engine: deterministic scoring + explainability | ⏳ |
| 9 | CV Analysis: PDF/DOCX/TXT parsing → structured profile → embedding | ⏳ |
| 10 | Frontend Dashboard: search, job card, job detail, saved, matches, profile | ⏳ |
| 11 | Job Alerts + scheduler + notification | ⏳ |
| 12 | Admin: source/crawler/AI/job statistics | ⏳ |
| 13 | Security + Performance audit | ⏳ |
| 14 | Production packaging: Docker, CI/CD, health checks, deployment docs | ⏳ |
| 15 | *(Deferred)* Multi-user Auth: register/login/JWT | ⏳ |

---

## 4. Quality Gate từng Phase

### Phase 1 — Foundation ✅

- [x] Backend khởi động thật bằng uvicorn, `GET /health` trả 200
- [x] `GET /health/ready` ping database thật và trả 503 khi không kết nối được
- [x] Frontend build production thành công (203 kB JS / 66 kB gzip)
- [x] `ruff check` PASS · `ruff format --check` PASS
- [x] `mypy --strict` PASS (31 file, 0 lỗi)
- [x] `pytest` PASS — 54 test
- [x] ESLint (`strictTypeChecked`) PASS
- [x] `tsc --noEmit` PASS
- [x] `vitest` PASS — 25 test
- [x] `npm audit` — 0 lỗ hổng
- [x] `docker-compose.yml` + Dockerfile viết đủ service — **đánh dấu UNVERIFIED** vì máy không có Docker

**Chưa đạt (chờ thao tác của người dùng):**
- [ ] Alembic migration chạy thật — cần mật khẩu MySQL trong `.env`. Migration đầu tiên thuộc Phase 3 (chưa có model nào ngoài `Base`).

### Phase 2 — Local Profile
- [ ] Local owner user tự seed khi khởi động
- [ ] `GET/PUT /api/profile` hoạt động, validate đầy đủ
- [ ] Skills và preferences CRUD hoạt động
- [ ] App từ chối khởi động khi `APP_ENV=production` + `SINGLE_USER_MODE=true`
- [ ] Tests pass

### Phase 3 — Job Data Model
- [ ] Tạo / đọc / search / filter / save job
- [ ] Index đầy đủ, không có N+1 query
- [ ] Full-text search hoạt động trên cả 2 dialect

### Phase 4 — Job Source System
- [ ] Ít nhất **1 source thật** chạy end-to-end (không phải mock)
- [ ] Source lỗi không làm chết pipeline
- [ ] Rate limit + retry + circuit breaker có test
- [ ] Mỗi adapter bị disable đều có lý do được document trong `docs/CRAWLERS.md`

### Phase 5 — Deduplication
- [ ] Cùng 1 job từ 2 nguồn → không tạo bản ghi trùng không kiểm soát
- [ ] Bản ghi trùng được đánh dấu `duplicate_of`, không xóa

### Phase 6 — AI Analysis
- [ ] Output luôn validate qua Pydantic schema
- [ ] Malformed JSON → retry → fallback → `status = AI_ANALYSIS_PENDING` (không mất job)
- [ ] Timeout / provider unavailable có test

### Phase 7 — Search
- [ ] Keyword search (vi/ko/en) hoạt động
- [ ] Semantic search hoạt động
- [ ] Hybrid ranking hoạt động
- [ ] Search API < 500ms trên dataset test

### Phase 8 — Matching
- [ ] Cùng candidate + job → **score xác định (deterministic)**
- [ ] Trả đủ strengths / gaps / explanation

### Phase 9 — CV
- [ ] Upload → parse → hiển thị structured profile → match với job
- [ ] File validation: extension, MIME, size, path traversal

### Phase 10 — Dashboard
- [ ] End-to-end user journey hoàn chỉnh trong browser

### Phase 11–14
- Xem chi tiết trong từng phase report.

---

## 5. Rủi ro đã xác định

| Rủi ro | Mức | Xử lý |
|---|---|---|
| Không verify được `docker compose up` vì thiếu Docker | Trung bình | Viết config đúng chuẩn, đánh dấu **UNVERIFIED** trong README, kèm hướng dẫn tự kiểm |
| Job sources Hàn Quốc phần lớn **không có API công khai** và ToS cấm scraping | **Cao** | Không hack. Adapter nào không hợp lệ → `disabled` + document lý do. Ưu tiên nguồn có Open API chính thức (Saramin Open API, WorkNet/data.go.kr) |
| Không có AI API key → không chạy được AI analysis | Cao | AI provider abstraction + provider `null`/local fallback; job không mất, chỉ ở trạng thái `AI_ANALYSIS_PENDING` |
| pgvector không chạy trên SQLite | Trung bình | `VectorStore` abstraction: pgvector (prod) / brute-force cosine (local, dataset nhỏ hợp lý cho single-user) |
| Windows + Unicode path gây lỗi tooling | Thấp | Quote path mọi nơi; test thực tế từng bước |
| Thông tin visa sai gây hậu quả pháp lý cho người dùng | **Cao** | Mọi output visa đều kèm disclaimer bắt buộc, không bao giờ khẳng định tính hợp pháp. Xem ADR-009 |

---

## 6. Nguyên tắc thi công

1. **Không fake dữ liệu.** Không fake job, fake AI score, fake crawler, fake API response.
2. Seed data chỉ tồn tại khi `APP_ENV=development`, và luôn gắn cờ `is_seed=true`.
3. Mỗi feature có test. Test fail → chẩn đoán → sửa → chạy lại. Không bỏ qua.
4. Không bypass CAPTCHA / anti-bot / authentication của bất kỳ nguồn nào.
5. Commit theo logical unit, không commit secrets.
6. Không chuyển phase khi Quality Gate chưa đạt.
