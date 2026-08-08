"""Fixture dùng chung cho toàn bộ test suite."""

from __future__ import annotations

# APP_ENV phải được đặt TRƯỚC khi import bất kỳ module nào của app, vì Settings
# đọc môi trường ngay lần khởi tạo đầu tiên và kết quả được cache.
import os

os.environ["APP_ENV"] = "test"
os.environ.setdefault("LOG_LEVEL", "warning")
os.environ.setdefault("LOG_FORMAT", "console")

from collections.abc import AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.core.db import check_database_health, dispose_engine
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture
def app(settings: Settings) -> Iterator[object]:
    """Instance FastAPI, tạo mới cho mỗi test để state không rò rỉ giữa các test."""
    yield create_app(settings)


@pytest.fixture
async def client(app: object) -> AsyncIterator[AsyncClient]:
    """HTTP client gọi thẳng vào ASGI app, không cần chạy server thật."""
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    await dispose_engine()


@pytest.fixture
async def require_mysql() -> None:
    """Bỏ qua test nếu MySQL chưa chạy hoặc chưa cấu hình.

    Không kết nối được database là tình huống môi trường bình thường trên máy
    dev mới, không phải lỗi của code — nên skip thay vì fail.
    """
    health = await check_database_health()
    if health["status"] != "up":
        pytest.skip(
            f"MySQL không sẵn sàng ({health.get('error')}). "
            "Chạy scripts/mysql_setup.sql và cấu hình TEST_DATABASE_URL trong .env."
        )
