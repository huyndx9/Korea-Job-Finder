"""Async database engine và session management (MySQL 8).

Engine được tạo lười (lazy) để việc import module không mở kết nối — quan
trọng cho test và cho các CLI script chỉ cần đọc cấu hình.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings
from app.core.errors import DatabaseUnavailableError
from app.core.logging import get_logger

log = get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def create_engine(settings: Settings) -> AsyncEngine:
    """Tạo async engine cho MySQL.

    `pool_pre_ping` là bắt buộc với MySQL: server đóng connection nhàn rỗi sau
    `wait_timeout` (mặc định 8 giờ), pre-ping giúp tránh lỗi "server has gone away".
    """
    connect_args: dict[str, Any] = {}

    return create_async_engine(
        settings.active_database_url,
        echo=settings.db_echo,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle,
        connect_args=connect_args,
    )


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings())
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,  # cho phép đọc field sau commit trong response
            autoflush=False,
        )
    return _session_factory


async def dispose_engine() -> None:
    """Đóng toàn bộ connection pool. Gọi khi ứng dụng shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
    _session_factory = None


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency cấp một session cho mỗi request.

    Commit khi request thành công, rollback khi có exception. Nhờ vậy các
    route handler không phải tự quản lý transaction.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def check_database_health() -> dict[str, Any]:
    """Ping database thật. Dùng cho endpoint /health.

    Trả về trạng thái thật, không bao giờ trả 'ok' cứng.
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT VERSION()"))
            version = result.scalar_one()
        return {"status": "up", "server_version": str(version)}
    except SQLAlchemyError as exc:
        log.warning("database_health_check_failed", error=str(exc))
        return {"status": "down", "error": type(exc).__name__}
    except Exception as exc:  # driver có thể ném lỗi ngoài SQLAlchemyError
        log.warning("database_health_check_failed", error=str(exc))
        return {"status": "down", "error": type(exc).__name__}


async def require_database() -> None:
    """Ném lỗi nếu database không dùng được. Dùng ở các luồng bắt buộc có DB."""
    health = await check_database_health()
    if health["status"] != "up":
        raise DatabaseUnavailableError(
            "Không kết nối được database MySQL. "
            "Kiểm tra service MySQL80 và DATABASE_URL trong .env.",
            details=health,
        )


async def check_database_charset() -> dict[str, Any]:
    """Xác minh database dùng utf8mb4.

    Model không khai báo charset ở cấp bảng (xem `app.models.base.Base`) mà kế
    thừa từ default của database. Nếu database bị tạo với utf8mb3 hoặc latin1
    thì tiếng Hàn và tiếng Việt có dấu sẽ bị hỏng ÂM THẦM — dữ liệu sai chỉ lộ
    ra rất lâu sau đó. Vì vậy phải kiểm tra tường minh lúc khởi động.
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME "
                        "FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = DATABASE()"
                    )
                )
            ).first()
    except Exception as exc:
        return {"status": "unknown", "error": type(exc).__name__}

    if row is None:
        return {"status": "unknown", "error": "no_database_selected"}

    charset, collation = str(row[0]), str(row[1])
    ok = charset == "utf8mb4"
    if not ok:
        log.error(
            "database_charset_invalid",
            charset=charset,
            collation=collation,
            detail=(
                "Database không dùng utf8mb4. Tiếng Hàn và tiếng Việt có dấu sẽ bị hỏng. "
                "Chạy: ALTER DATABASE <ten_db> CHARACTER SET utf8mb4 "
                "COLLATE utf8mb4_unicode_ci;"
            ),
        )
    return {"status": "ok" if ok else "invalid", "charset": charset, "collation": collation}
