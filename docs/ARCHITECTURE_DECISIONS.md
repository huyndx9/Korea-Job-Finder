# Architecture Decision Records

Mỗi quyết định kỹ thuật đáng kể được ghi lại ở đây kèm bối cảnh và đánh đổi.
Định dạng: Bối cảnh → Quyết định → Hệ quả → Đường thoát.

---

## ADR-001 — Monorepo với npm workspaces, không dùng Nx/Turborepo

**Ngày:** 2026-08-08 · **Trạng thái:** Accepted

**Bối cảnh.** Dự án có 2 ứng dụng (`apps/web`, `apps/api`) khác ngôn ngữ. Frontend cần chia sẻ kiểu dữ liệu với backend.

**Quyết định.** Dùng npm workspaces thuần. Không thêm Nx, Turborepo hay Lerna.

**Lý do.** Chỉ có một package JavaScript duy nhất. Lợi ích chính của Nx/Turborepo là cache build và task graph giữa nhiều package — thứ chưa tồn tại ở đây. Thêm chúng lúc này là chi phí cấu hình mà không có lợi ích tương ứng.

**Hệ quả.** Backend là Python nên không nằm trong workspace graph; điều phối chạy qua `make.ps1` / `Makefile`.

**Đường thoát.** Khi có từ 3 package JS trở lên và thời gian build vượt ~30s, cân nhắc lại.

---

## ADR-002 — MySQL 8.0 là database duy nhất, thay cho PostgreSQL + pgvector

**Ngày:** 2026-08-08 · **Trạng thái:** Accepted · **Thay thế:** kế hoạch dual-dialect ban đầu

**Bối cảnh.** Thiết kế ban đầu chọn PostgreSQL + pgvector cho semantic search. Audit môi trường cho thấy máy phát triển:
- không có Docker,
- không có PostgreSQL,
- **có sẵn MySQL 8.0.46 đang chạy**.

Người dùng xác nhận muốn dùng MySQL.

**Quyết định.** MySQL 8.0 là database duy nhất cho dev, test và production. Không viết lớp trừu tượng đa dialect.

**Đánh đổi đã cân nhắc.**

| Tiêu chí | PostgreSQL | MySQL 8.0 | Đánh giá |
|---|---|---|---|
| Full-text tiếng Hàn | `tsvector` | `FULLTEXT ... WITH PARSER ngram` | Tương đương cho nhu cầu này |
| JSON | JSONB (có index) | JSON (index qua generated column) | MySQL kém hơn chút, chấp nhận được |
| Mảng | native ARRAY | không có → dùng JSON | Ảnh hưởng nhỏ |
| **Vector / ANN index** | **pgvector + HNSW** | **không có kiểu VECTOR trước 9.0** | **Điểm mất thật sự** |

**Hệ quả.**
- Embedding lưu dạng float32 nhị phân (`LONGBLOB`, xem `app/models/base.py::Vector`).
- Semantic search tính cosine similarity bằng numpy trong ứng dụng, độ phức tạp O(n).
- Ở quy mô single-user (~10⁴–10⁵ job) chi phí ước tính 20–80ms — vẫn nằm trong ngân sách 500ms của Search API. Con số này **phải được đo lại thật ở Phase 7**, không được coi là đã chứng minh.
- Lọc thô bằng SQL (location, industry, ngày đăng) chạy trước, cosine chỉ tính trên tập đã lọc.

**Cái nhận lại.** Bỏ được toàn bộ lớp trừu tượng dual-dialect: không `TypeDecorator` theo dialect, không hai bản implementation cho search layer, test chạy trên đúng engine của production.

**Đường thoát.** Khi số job vượt ~500k hoặc p95 search vượt 500ms: nâng lên MySQL 9.x (có kiểu `VECTOR`), hoặc tách vector index sang một store chuyên dụng. Ranh giới `search/` được thiết kế để chỉ phải thay phần bên trong.

---

## ADR-003 — Hoãn authentication, chạy Single-User Mode ở v1

**Ngày:** 2026-08-08 · **Trạng thái:** Accepted

**Bối cảnh.** Người dùng yêu cầu: *"tôi muốn dùng app để bản thân sử dụng trước nên chưa cần tính năng đăng nhập"*.

**Quyết định.** Không implement register/login/JWT ở v1. Mọi request được gán cho một "local owner user" duy nhất.

**Cách làm.** Giữ nguyên dependency `get_current_user()` ở mọi endpoint. Ở single-user mode nó trả về local owner thay vì xác thực token. Toàn bộ tầng service và repository vẫn nhận `user_id` như bình thường.

**Lý do giữ dependency.** Khi bổ sung auth ở Phase 15, chỉ cần thay thân một hàm. Nếu bỏ hẳn `user_id` khỏi tầng dưới thì sau này phải sửa lại toàn bộ business logic — nợ kỹ thuật đắt hơn nhiều so với chi phí giữ tham số ngay từ đầu.

**Rào an toàn (bắt buộc, đã có test).**
- `APP_ENV=production` + `SINGLE_USER_MODE=true` → **ứng dụng từ chối khởi động**.
- Single-user mode chỉ cho phép `API_HOST` là loopback.

Kiểm tra thực hiện lúc khởi tạo `Settings` (fail-fast), không phải lúc phục vụ request.

**Rủi ro còn lại.** Bất kỳ tiến trình nào trên chính máy đó đều gọi được API. Chấp nhận được với máy cá nhân một người dùng; **không** chấp nhận được nếu máy dùng chung.

---

## ADR-004 — `make.ps1` cho Windows, giữ song song `Makefile`

**Ngày:** 2026-08-08 · **Trạng thái:** Accepted

**Bối cảnh.** Máy phát triển là Windows, không có `make`. Đặc tả yêu cầu có Makefile.

**Quyết định.** Viết cả hai, cùng bộ target tên giống nhau. `make.ps1` là đường chạy chính trên Windows; `Makefile` phục vụ Linux/macOS/CI.

**Hệ quả.** Có trùng lặp, phải sửa cả hai khi thêm target. Chấp nhận vì số target ít và ổn định. Lựa chọn thay thế (viết task runner bằng Python) sẽ thêm một tầng gián tiếp cho vấn đề không xứng đáng.

---

## ADR-005 — Task queue trừu tượng hoá, mặc định chạy in-process

**Ngày:** 2026-08-08 · **Trạng thái:** Accepted

**Bối cảnh.** Máy không có Redis. Đặc tả yêu cầu Celery/RQ + Redis, và cấm chạy crawler nặng trong request của FastAPI.

**Quyết định.** Định nghĩa protocol `TaskQueue` với hai implementation:
- `ThreadTaskQueue` — worker in-process, dùng khi `REDIS_URL` trống.
- `CeleryTaskQueue` — dùng khi có `REDIS_URL`.

Cả hai đều ghi trạng thái vào bảng `task_runs`, nên admin dashboard đọc được số liệu thật ở cả hai chế độ.

**Lý do.** Yêu cầu thật sự là "crawler không được chặn HTTP request", không phải "phải dùng Redis". `ThreadTaskQueue` thoả yêu cầu đó mà không cần thêm hạ tầng.

**Hệ quả.** `ThreadTaskQueue` mất task đang chạy dở nếu tiến trình chết. Chấp nhận với single-user: crawler chạy lại theo lịch sẽ thu thập bù. Production dùng Celery.

---

## ADR-006 — Điểm matching tính xác định, LLM chỉ diễn giải

**Ngày:** 2026-08-08 · **Trạng thái:** Accepted

**Bối cảnh.** Đặc tả yêu cầu cùng candidate + job phải cho ra cùng một điểm số.

**Quyết định.** Điểm số tính hoàn toàn bằng thuật toán có trọng số. LLM **không tham gia tính điểm**, chỉ sinh phần diễn giải bằng ngôn ngữ tự nhiên, và phần đó không được phép thay đổi con số.

**Lý do.** LLM không ổn định giữa các lần gọi. Người dùng ra quyết định nghề nghiệp dựa trên con số này — điểm nhảy từ 87% xuống 72% khi tải lại trang sẽ phá huỷ niềm tin, và đúng ra là như vậy.

**Hệ quả.** Mỗi chiều đánh giá trả về `DimensionScore {score, weight, strengths[], gaps[], evidence[]}`. Phần giải thích là dữ liệu có cấu trúc, dùng được ngay cả khi không có AI provider nào được cấu hình.

---

## ADR-007 — `NullProvider` báo lỗi thay vì trả kết quả giả

**Ngày:** 2026-08-08 · **Trạng thái:** Accepted

**Bối cảnh.** Chưa có AI API key. Cần hệ thống vẫn dùng được.

**Quyết định.** `AI_PROVIDER=null` khiến `NullProvider` ném `AIUnavailableError`. Job chuyển sang trạng thái `AI_ANALYSIS_PENDING` và sẽ được phân tích lại khi có key.

**Lý do.** Cách làm thay thế — trả về điểm mặc định hoặc phân tích rỗng — sẽ tạo ra dữ liệu trông như thật nhưng vô nghĩa. Người dùng không phân biệt được "AI đánh giá job này 50%" với "AI chưa chạy". Trạng thái pending tường minh thì trung thực.

**Hệ quả.** UI phải xử lý được job chưa có phân tích AI. Đây là yêu cầu bắt buộc của Phase 10, không phải trường hợp biên.

---

## ADR-008 — Che dữ liệu nhạy cảm ở tầng logging processor

**Ngày:** 2026-08-08 · **Trạng thái:** Accepted

**Bối cảnh.** Đặc tả cấm log password, token và dữ liệu CV.

**Quyết định.** Cài đặt bằng structlog processor chạy trên **mọi** log event, khớp theo mẫu tên khoá, đệ quy vào dict/list lồng nhau.

**Lý do.** Cách thay thế — dựa vào kỷ luật của người viết code — sẽ hỏng. Rò rỉ dữ liệu thường xảy ra khi ai đó log nguyên một object để debug rồi quên xoá. Che ở tầng processor khiến lỗi đó không gây hậu quả.

**Hệ quả.** Có thể che nhầm field vô hại có tên chứa `email`/`token`. Đánh đổi đúng chiều: log kém chi tiết hơn thì phiền, log rò rỉ dữ liệu thì nguy hiểm.

---

## ADR-009 — Thông tin visa luôn kèm cảnh báo, không bao giờ khẳng định

**Ngày:** 2026-08-08 · **Trạng thái:** Accepted

**Bối cảnh.** Hệ thống suy luận khả năng tương thích visa từ nội dung tin tuyển dụng. Người dùng có thể ra quyết định nhập cư dựa trên đó.

**Quyết định.** Mọi output liên quan đến visa đều kèm cảnh báo bắt buộc. Hệ thống **không bao giờ** phát biểu rằng người dùng đủ điều kiện làm việc hợp pháp.

Ngôn từ chuẩn: *"Dựa trên thông tin có trong tin tuyển dụng, vị trí này có vẻ phù hợp. Hãy tự kiểm tra lại quy định xuất nhập cảnh hiện hành trước khi nhận việc."*

Khi có nguồn chính thức, lưu `visa_source` và `visa_checked_at` để người dùng tự đối chiếu.

**Lý do.** Tin tuyển dụng không phải văn bản pháp lý và thường sai. Sai sót ở đây gây hậu quả nghiêm trọng cho người dùng, khác hẳn với gợi ý sai một công việc không phù hợp.

**Hệ quả.** Ràng buộc này áp cho cả template prompt của AI, không chỉ cho phần hiển thị.

---

## ADR-010 — Không khai báo charset ở cấp bảng, kiểm tra lúc khởi động

**Ngày:** 2026-08-08 · **Trạng thái:** Accepted

**Bối cảnh.** Dữ liệu gồm tiếng Việt có dấu, Hangul và emoji — bắt buộc `utf8mb4`. Cách thông thường là đặt `__table_args__ = {"mysql_charset": "utf8mb4"}` trên Base.

**Quyết định.** Không đặt. Để bảng kế thừa charset mặc định của database, rồi xác minh bằng `check_database_charset()` lúc khởi động.

**Lý do.** `__table_args__` đặt trên Base sẽ bị model con ghi đè mất khi chúng cần khai báo `Index` hoặc `UniqueConstraint` — mà hầu hết model đều cần. Charset mất đi trong im lặng và chỉ lộ ra khi dữ liệu đã hỏng. Kiểm tra tường minh lúc khởi động phát hiện sớm và cho thông báo sửa chữa cụ thể.

**Hệ quả.** `scripts/mysql_setup.sql` phải tạo database với `CHARACTER SET utf8mb4`. Kiểm tra lúc khởi động là biện pháp bảo vệ nếu bước đó bị bỏ sót.
