# VietJob Korea AI 🇻🇳🇰🇷

Nền tảng tổng hợp việc làm và AI matching dành cho người Việt tìm việc tại Hàn Quốc.

Thay vì mở 10 website tuyển dụng khác nhau, bạn khai báo hồ sơ một lần — hệ thống thu thập tin tuyển dụng từ nhiều nguồn, chuẩn hoá, khử trùng lặp, dùng AI phân tích yêu cầu, rồi chấm điểm mức độ phù hợp kèm giải thích cụ thể.

> **Trạng thái: đang phát triển — Phase 1/14 hoàn thành.**
> Xem [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) để biết lộ trình và những gì đã/chưa làm.

---

## Mục lục

- [Tính năng](#tính-năng)
- [Kiến trúc](#kiến-trúc)
- [Công nghệ](#công-nghệ)
- [Cài đặt](#cài-đặt)
- [Biến môi trường](#biến-môi-trường)
- [Lệnh phát triển](#lệnh-phát-triển)
- [Kiểm thử](#kiểm-thử)
- [Kiến trúc crawler](#kiến-trúc-crawler)
- [Kiến trúc AI](#kiến-trúc-ai)
- [Docker](#docker)
- [Lộ trình](#lộ-trình)
- [Giới hạn đã biết](#giới-hạn-đã-biết)
- [Lưu ý pháp lý về nguồn dữ liệu](#lưu-ý-pháp-lý-về-nguồn-dữ-liệu)

---

## Tính năng

| | Tính năng | Phase | Trạng thái |
|---|---|---|---|
| 🏗️ | Nền tảng: API, database, frontend, CI tooling | 1 | ✅ Xong |
| 👤 | Hồ sơ cá nhân: visa, TOPIK, kỹ năng, mong muốn | 2 | ⏳ |
| 💼 | Mô hình dữ liệu việc làm + tìm kiếm + lưu job | 3 | ⏳ |
| 🔌 | Thu thập từ nhiều nguồn tuyển dụng | 4 | ⏳ |
| 🧹 | Chuẩn hoá + khử trùng lặp 4 tầng | 5 | ⏳ |
| 🤖 | AI phân tích JD: visa, TOPIK, kỹ năng, độ thân thiện với người nước ngoài | 6 | ⏳ |
| 🔍 | Tìm kiếm đa ngôn ngữ (Việt / Hàn / Anh) + semantic search | 7 | ⏳ |
| 🎯 | Chấm điểm phù hợp kèm giải thích điểm mạnh / điểm thiếu | 8 | ⏳ |
| 📄 | Upload CV → phân tích → đối chiếu với job | 9 | ⏳ |
| 📊 | Dashboard đầy đủ | 10 | ⏳ |
| 🔔 | Job alert theo lịch | 11 | ⏳ |
| ⚙️ | Admin: giám sát nguồn, crawler, AI | 12 | ⏳ |

---

## Kiến trúc

```
apps/web (React + Vite)
      │  HTTP/JSON
apps/api (FastAPI)
      │
      ├─ api/          routers, dependencies
      ├─ services/     business logic
      ├─ repositories/ truy cập DB
      ├─ sources/      JobSourceAdapter + registry
      ├─ pipeline/     normalize → dedupe → analyze → embed
      ├─ ai/           AIProvider abstraction
      ├─ matching/     thuật toán chấm điểm xác định
      ├─ search/       keyword + semantic + hybrid ranking
      └─ workers/      TaskQueue abstraction
      │
   MySQL 8.0
```

Chi tiết: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
Các quyết định kỹ thuật và lý do: [docs/ARCHITECTURE_DECISIONS.md](docs/ARCHITECTURE_DECISIONS.md).

---

## Công nghệ

**Frontend** — React 18, TypeScript 5.7, Vite 8, Tailwind CSS 4, TanStack Query, React Router 7, Zod, React Hook Form, Zustand, Lucide

**Backend** — Python 3.14, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic, httpx, BeautifulSoup, structlog, tenacity

**Database** — MySQL 8.0 (InnoDB, utf8mb4, FULLTEXT với parser ngram)

**AI** — abstraction hỗ trợ Anthropic / OpenAI / Gemini / model cục bộ; embedding qua sentence-transformers

**Chất lượng** — pytest, Vitest, Testing Library, Ruff, MyPy (strict), ESLint (strictTypeChecked), Prettier

---

## Cài đặt

### Yêu cầu

- **Node.js** ≥ 20 (đã kiểm chứng trên 24.18)
- **Python** ≥ 3.12 (đã kiểm chứng trên 3.14.6)
- **MySQL** 8.0 đang chạy

### 1. Cài dependency

```powershell
.\make.ps1 install
```

Lệnh này tạo virtualenv Python, cài dependency backend + frontend, và tạo `.env` từ `.env.example`.

> Trên Linux/macOS dùng `make install`.

### 2. Tạo database

Copy `scripts/mysql_setup.sql` thành `scripts/mysql_setup.local.sql` (file `.local.sql` đã được gitignore), thay `CHANGE_ME_STRONG_PASSWORD` bằng mật khẩu bạn tự chọn, rồi chạy — MySQL sẽ hỏi mật khẩu **root**:

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p -e "source scripts/mysql_setup.local.sql"
```

> Dùng `-e "source ..."` chứ **không** dùng `< file`: PowerShell không hỗ trợ toán tử `<`.
> Trên Linux/macOS thì `mysql -u root -p < scripts/mysql_setup.local.sql` chạy bình thường.

Script tạo hai database (`vietjob`, `vietjob_test`) với charset `utf8mb4` và một user riêng cho ứng dụng.

### 3. Cấu hình kết nối

Mở `.env`, điền cùng mật khẩu đó:

```env
DATABASE_URL=mysql+asyncmy://vietjob:MAT_KHAU_CUA_BAN@127.0.0.1:3306/vietjob?charset=utf8mb4
TEST_DATABASE_URL=mysql+asyncmy://vietjob:MAT_KHAU_CUA_BAN@127.0.0.1:3306/vietjob_test?charset=utf8mb4
```

> Nếu mật khẩu chứa `@ : / ? #` thì phải URL-encode (ví dụ `@` → `%40`). Cách đơn giản nhất là chỉ dùng chữ và số.

Kiểm tra kết nối:

```powershell
.\make.ps1 db-check
```

### 4. Chạy migration

```powershell
.\make.ps1 migrate
```

### 5. Khởi động

Mở hai cửa sổ terminal:

```powershell
.\make.ps1 api
```

```powershell
.\make.ps1 web
```

- Frontend: http://localhost:5173
- API docs: http://127.0.0.1:8000/docs

Trang chủ hiển thị trạng thái hệ thống — nếu MySQL kết nối được, mục "MySQL" sẽ hiện phiên bản server thật.

---

## Biến môi trường

Danh sách đầy đủ kèm chú thích nằm trong [`.env.example`](.env.example). Những biến quan trọng nhất:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `APP_ENV` | `development` | `development` / `test` / `production` |
| `SINGLE_USER_MODE` | `true` | Bỏ qua đăng nhập. **Bắt buộc `false` ở production.** |
| `DATABASE_URL` | — | Chuỗi kết nối MySQL |
| `TEST_DATABASE_URL` | — | Database cho test — **sẽ bị xoá sạch mỗi lần chạy test** |
| `AI_PROVIDER` | `null` | `anthropic` / `openai` / `gemini` / `local` / `null` |
| `EMBEDDING_PROVIDER` | `local` | `local` chạy trên máy, không cần API key |
| `REDIS_URL` | *(trống)* | Trống → dùng worker in-process |

**Không bao giờ commit `.env`.** File đã nằm trong `.gitignore`.

---

## Lệnh phát triển

```powershell
.\make.ps1 help          # Xem toàn bộ lệnh
.\make.ps1 api           # Chạy backend
.\make.ps1 web           # Chạy frontend
.\make.ps1 test          # Chạy toàn bộ test
.\make.ps1 lint          # Ruff + ESLint
.\make.ps1 typecheck     # MyPy + tsc
.\make.ps1 format        # Tự động format
.\make.ps1 check         # lint + typecheck + test (chạy trước khi commit)
.\make.ps1 migration "mo ta thay doi"   # Sinh migration mới
.\make.ps1 migrate       # Áp dụng migration
```

Trên Linux/macOS: thay `.\make.ps1 X` bằng `make X`.

---

## Kiểm thử

```powershell
.\make.ps1 test-api      # pytest
.\make.ps1 test-web      # vitest
```

Test cần MySQL sẽ **tự động bỏ qua** nếu không kết nối được, kèm thông báo hướng dẫn — không kết nối được database trên máy mới là chuyện bình thường, không phải lỗi code.

Test không bao giờ chạy trên database chính: `Settings` từ chối khởi động nếu `TEST_DATABASE_URL` và `DATABASE_URL` trỏ cùng một database.

---

## Kiến trúc crawler

*Sẽ triển khai ở Phase 4 — chi tiết trong `docs/CRAWLERS.md`.*

Mọi nguồn tuyển dụng đều đi qua interface `JobSourceAdapter`. Nguyên tắc bắt buộc:

- **Không** vượt CAPTCHA, không vượt anti-bot, không vượt authentication, không truy cập dữ liệu riêng tư.
- Nguồn nào không có API công khai hoặc điều khoản không cho phép thu thập → adapter ở trạng thái `disabled` kèm lý do được ghi rõ.
- Mỗi nguồn có rate limit, timeout, retry với exponential backoff, và circuit breaker riêng.
- **Một nguồn chết không làm chết pipeline.**

---

## Kiến trúc AI

*Sẽ triển khai ở Phase 6 — chi tiết trong `docs/AI.md`.*

- Ứng dụng phụ thuộc vào interface `AIProvider`, không phụ thuộc nhà cung cấp cụ thể.
- Mọi output của LLM đều validate bằng Pydantic schema. Không tin raw output.
- Malformed JSON → retry → hết retry thì đưa vào dead-letter và đặt job ở trạng thái `AI_ANALYSIS_PENDING`. **Không bao giờ mất job.**
- Khi `AI_PROVIDER=null`, hệ thống **không** sinh kết quả giả — job đứng ở trạng thái pending cho tới khi có API key.
- **Điểm matching không do LLM tính** (xem ADR-006), nên cùng hồ sơ + cùng job luôn cho cùng một điểm.

---

## Docker

⚠️ **Chưa kiểm chứng.** Docker không được cài trên máy phát triển nên `docker compose up` chưa từng chạy thật. File cấu hình được viết theo chuẩn nhưng phải coi là chưa test cho tới khi có ai đó chạy thành công.

Đường chạy được kiểm chứng là chạy trực tiếp trên máy (`.\make.ps1`).

---

## Lộ trình

| Phase | Nội dung | Trạng thái |
|---|---|---|
| 0 | Audit + tài liệu kiến trúc | ✅ |
| 1 | Nền tảng: API, DB, frontend, tooling | ✅ |
| 2 | Hồ sơ cá nhân (chưa cần đăng nhập) | ⏳ |
| 3 | Mô hình dữ liệu việc làm | ⏳ |
| 4 | Hệ thống nguồn tuyển dụng | ⏳ |
| 5 | Chuẩn hoá + khử trùng lặp | ⏳ |
| 6 | AI phân tích JD | ⏳ |
| 7 | Tìm kiếm + semantic search | ⏳ |
| 8 | Engine chấm điểm phù hợp | ⏳ |
| 9 | Phân tích CV | ⏳ |
| 10 | Dashboard | ⏳ |
| 11 | Job alert | ⏳ |
| 12 | Admin | ⏳ |
| 13 | Rà soát bảo mật + hiệu năng | ⏳ |
| 14 | Đóng gói production | ⏳ |
| 15 | Đăng nhập nhiều người dùng *(hoãn theo yêu cầu)* | ⏳ |

---

## Giới hạn đã biết

1. **Không có ANN index cho vector.** MySQL 8.0 chưa có kiểu `VECTOR`. Semantic search tính cosine bằng numpy, độ phức tạp O(n). Đủ nhanh ở quy mô single-user; cần đo lại ở Phase 7. Xem [ADR-002](docs/ARCHITECTURE_DECISIONS.md#adr-002).

2. **Không có authentication.** v1 chạy single-user mode, mọi tiến trình trên cùng máy đều gọi được API. Ứng dụng từ chối khởi động nếu bật chế độ này ở production. Xem [ADR-003](docs/ARCHITECTURE_DECISIONS.md#adr-003).

3. **Cấu hình Docker chưa được kiểm chứng** (không có Docker trên máy phát triển).

4. **Nguồn tuyển dụng phụ thuộc điều khoản của từng bên.** Phần lớn website tuyển dụng Hàn Quốc không có API công khai. Chỉ những nguồn có API chính thức hoặc cho phép thu thập rõ ràng mới được bật.

5. **AI cần API key.** Không có key thì job vẫn được thu thập và tìm kiếm được, nhưng không có phân tích AI và không có điểm matching dựa trên AI.

---

## Lưu ý pháp lý về nguồn dữ liệu

Dự án này thu thập tin tuyển dụng **được đăng công khai** để giúp người tìm việc phát hiện cơ hội. Ràng buộc tự đặt ra:

- Tôn trọng `robots.txt` và điều khoản sử dụng của từng nguồn.
- Không vượt qua bất kỳ biện pháp kiểm soát truy cập nào (CAPTCHA, anti-bot, đăng nhập).
- Không thu thập thông tin cá nhân, chỉ lấy nội dung tin tuyển dụng.
- Rate limit ở mức lịch sự, khai báo User-Agent trung thực kèm thông tin liên hệ.
- Luôn dẫn về `source_url` gốc — người dùng nộp hồ sơ trên website gốc, hệ thống này **không** thay mặt ai nộp đơn.
- Nguồn nào không cho phép thu thập thì adapter bị tắt, kèm lý do ghi rõ trong `docs/CRAWLERS.md`.

**Thông tin về visa chỉ mang tính tham khảo, không phải tư vấn pháp lý.** Hãy luôn tự kiểm tra lại với cơ quan xuất nhập cảnh Hàn Quốc trước khi ra quyết định. Xem [ADR-009](docs/ARCHITECTURE_DECISIONS.md#adr-009).
