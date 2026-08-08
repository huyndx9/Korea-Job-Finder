"""Cấu hình ứng dụng.

Toàn bộ cấu hình đọc từ biến môi trường / file `.env`. Không có secret nào
được hard-code. Các bất biến an toàn được kiểm tra ngay lúc khởi tạo Settings
(fail-fast) thay vì để lỗi xuất hiện lúc runtime.
"""

from __future__ import annotations

import functools
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api/app/core/config.py -> parents[2] = apps/api, parents[4] = repo root
API_ROOT: Path = Path(__file__).resolve().parents[2]
REPO_ROOT: Path = Path(__file__).resolve().parents[4]


class AppEnv(StrEnum):
    development = "development"
    test = "test"
    production = "production"


class AIProviderName(StrEnum):
    anthropic = "anthropic"
    openai = "openai"
    gemini = "gemini"
    local = "local"
    null = "null"


class EmbeddingProviderName(StrEnum):
    local = "local"
    openai = "openai"
    null = "null"


class LogFormat(StrEnum):
    json = "json"
    console = "console"


class ConfigurationError(RuntimeError):
    """Cấu hình không hợp lệ. Luôn ném ra lúc khởi động, không bao giờ lúc phục vụ request."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # .env ở gốc monorepo được ưu tiên; apps/api/.env dùng để override cục bộ.
        env_file=(REPO_ROOT / ".env", API_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Application ----
    app_env: AppEnv = AppEnv.development
    app_name: str = "VietJob Korea AI"
    app_debug: bool = False
    single_user_mode: bool = True

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Lối thoát cho single-user mode chạy trong container.
    #
    # Tiến trình trong container BẮT BUỘC bind 0.0.0.0, nếu không cổng publish
    # sẽ không nhận được kết nối — bind loopback bên trong container chỉ nghe
    # được từ chính container đó. Nhưng vì single-user mode không có
    # authentication, việc mở bind ra ngoài phải là quyết định có ý thức chứ
    # không được ngầm định.
    #
    # Bật cờ này CHỈ khi ranh giới mạng được đảm bảo ở tầng khác — ví dụ
    # docker-compose publish cổng ở dạng `127.0.0.1:8000:8000`, tức là chỉ máy
    # chủ truy cập được. Không bao giờ bật khi cổng mở ra toàn mạng.
    single_user_allow_external_bind: bool = False

    # ---- Database ----
    database_url: str = "mysql+asyncmy://vietjob:@127.0.0.1:3306/vietjob?charset=utf8mb4"
    test_database_url: str = "mysql+asyncmy://vietjob:@127.0.0.1:3306/vietjob_test?charset=utf8mb4"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle: int = 3600
    db_echo: bool = False

    # ---- Redis / task queue ----
    redis_url: str = ""

    # ---- AI ----
    ai_provider: AIProviderName = AIProviderName.null
    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_model: str = "claude-sonnet-5"
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-4o-mini"
    google_api_key: SecretStr = SecretStr("")
    gemini_model: str = "gemini-2.0-flash"
    ai_timeout_seconds: float = 60.0
    ai_max_retries: int = 3

    # ---- Embeddings ----
    embedding_provider: EmbeddingProviderName = EmbeddingProviderName.local
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384

    # ---- Job sources ----
    saramin_api_key: SecretStr = SecretStr("")
    worknet_api_key: SecretStr = SecretStr("")
    crawler_user_agent: str = "VietJobKoreaAI/0.1"
    crawler_request_timeout: float = 30.0
    crawler_rate_limit_per_minute: int = 20
    crawler_max_retries: int = 3
    crawler_respect_robots_txt: bool = True

    # ---- Resume ----
    resume_storage_dir: Path = Field(default=Path("./data/resumes"))
    resume_max_size_mb: int = 10

    # ---- SMTP ----
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = ""
    smtp_use_tls: bool = True

    # ---- Observability ----
    log_level: str = "info"
    log_format: LogFormat = LogFormat.console
    sentry_dsn: str = ""

    # ------------------------------------------------------------------
    # Bất biến an toàn — kiểm tra lúc khởi động
    # ------------------------------------------------------------------
    @model_validator(mode="after")
    def _enforce_safety_invariants(self) -> Self:
        if self.app_env is AppEnv.production and self.single_user_mode:
            raise ConfigurationError(
                "SINGLE_USER_MODE=true không được dùng với APP_ENV=production. "
                "Chế độ single-user bỏ qua authentication nên mọi request đều được coi "
                "là của chủ máy — public deployment sẽ để lộ toàn bộ dữ liệu. "
                "Hãy implement authentication (Phase 15) trước khi deploy production."
            )

        if (
            self.single_user_mode
            and not self.single_user_allow_external_bind
            and self.api_host not in {"127.0.0.1", "localhost", "::1"}
        ):
            raise ConfigurationError(
                f"SINGLE_USER_MODE=true yêu cầu API_HOST là loopback, đang là {self.api_host!r}. "
                "Không có authentication thì bind ra ngoài loopback là để ngỏ dữ liệu cho "
                "mọi máy trong cùng mạng. Nếu đang chạy trong container và ranh giới mạng "
                "đã được đảm bảo ở tầng khác, đặt SINGLE_USER_ALLOW_EXTERNAL_BIND=true."
            )

        if self.app_env is AppEnv.production and self.app_debug:
            raise ConfigurationError("APP_DEBUG=true không được bật ở production.")

        # Ngăn test xoá nhầm database thật.
        if _db_name(self.test_database_url) == _db_name(self.database_url):
            raise ConfigurationError(
                "TEST_DATABASE_URL và DATABASE_URL đang trỏ cùng một database "
                f"({_db_name(self.database_url)!r}). Test sẽ xoá sạch dữ liệu — "
                "phải dùng database riêng."
            )

        if not self.database_url.startswith("mysql+"):
            scheme = self.database_url.split(":", 1)[0]
            raise ConfigurationError(
                f"Dự án chỉ hỗ trợ MySQL, DATABASE_URL đang là {scheme!r}. "
                "Xem docs/ARCHITECTURE_DECISIONS.md (ADR-002)."
            )

        return self

    # ------------------------------------------------------------------
    # Thuộc tính dẫn xuất
    # ------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.app_env is AppEnv.production

    @property
    def is_testing(self) -> bool:
        return self.app_env is AppEnv.test

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins đọc từ chuỗi phân tách bằng dấu phẩy.

        Khai báo kiểu `str` thay vì `list[str]` là có chủ đích: pydantic-settings
        cố parse JSON cho field kiểu list, khiến `a,b` trở thành lỗi khó hiểu.
        """
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def active_database_url(self) -> str:
        """URL database thực dùng — tự chuyển sang test DB khi APP_ENV=test."""
        return self.test_database_url if self.is_testing else self.database_url

    @property
    def sync_database_url(self) -> str:
        """URL driver đồng bộ cho Alembic (Alembic không chạy async driver)."""
        return self.active_database_url.replace("mysql+asyncmy://", "mysql+pymysql://").replace(
            "mysql+aiomysql://", "mysql+pymysql://"
        )

    @property
    def use_celery(self) -> bool:
        """Chỉ dùng Celery khi có Redis; ngược lại chạy ThreadTaskQueue in-process."""
        return bool(self.redis_url.strip())

    @property
    def resume_max_size_bytes(self) -> int:
        return self.resume_max_size_mb * 1024 * 1024

    @property
    def resume_dir(self) -> Path:
        """Thư mục lưu CV, luôn trả về đường dẫn tuyệt đối đã chuẩn hoá."""
        path = self.resume_storage_dir
        if not path.is_absolute():
            path = REPO_ROOT / path
        return path.resolve()


def _db_name(url: str) -> str:
    """Lấy tên database từ SQLAlchemy URL, bỏ qua query string."""
    tail = url.rsplit("/", 1)[-1]
    return tail.split("?", 1)[0]


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Settings dùng chung toàn ứng dụng (đọc `.env` đúng một lần).

    Cache được để test có thể gọi `get_settings.cache_clear()` sau khi đổi
    biến môi trường.
    """
    return Settings()
