"""Nền tảng cho SQLAlchemy ORM models (MySQL 8 / InnoDB / utf8mb4)."""

from __future__ import annotations

import array
import datetime as dt
from typing import Any

from sqlalchemy import MetaData
from sqlalchemy.dialects.mysql import DATETIME, LONGBLOB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

# Đặt tên constraint theo quy ước để Alembic sinh migration ổn định.
# Không có phần này, MySQL tự sinh tên ngẫu nhiên và autogenerate sẽ tạo ra
# các diff giả mỗi lần chạy.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> dt.datetime:
    """Thời điểm hiện tại theo UTC, dạng naive.

    MySQL DATETIME không lưu timezone. Quy ước toàn dự án: mọi giá trị thời gian
    trong DB đều là UTC và naive; việc chuyển sang giờ địa phương do frontend làm.
    """
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


class Vector(TypeDecorator[list[float]]):
    """Lưu vector embedding dưới dạng float32 nhị phân đóng gói.

    MySQL 8.0 chưa có kiểu VECTOR (chỉ từ 9.0) và không có ANN index. Ta lưu
    embedding dạng blob rồi tính cosine similarity bằng numpy trong ứng dụng.
    Xem ADR-002 về đánh đổi và đường nâng cấp.

    float32 thay vì float64: giảm một nửa dung lượng, sai số không đáng kể với
    cosine similarity (embedding vốn chỉ có ~7 chữ số ý nghĩa).
    """

    impl = LONGBLOB
    cache_ok = True

    def process_bind_param(self, value: list[float] | None, dialect: Any) -> bytes | None:
        if value is None:
            return None
        return array.array("f", value).tobytes()

    def process_result_value(self, value: bytes | None, dialect: Any) -> list[float] | None:
        if value is None:
            return None
        buf = array.array("f")
        buf.frombytes(value)
        return list(buf)


class Base(DeclarativeBase):
    """Base class cho mọi ORM model.

    Charset và storage engine KHÔNG khai báo ở `__table_args__`. Lý do: đặt
    `__table_args__` trên Base thì mọi model muốn thêm Index hay UniqueConstraint
    sẽ phải tự ghi đè và vô tình làm mất phần charset. Thay vào đó ta để MySQL
    kế thừa từ default của database (`CREATE DATABASE ... CHARACTER SET utf8mb4`,
    xem `scripts/mysql_setup.sql`) và kiểm tra lại bằng
    `app.core.db.check_database_charset()` lúc khởi động.

    InnoDB là storage engine mặc định của MySQL 8 nên cũng không cần khai báo.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    def __repr__(self) -> str:
        pk = getattr(self, "id", None)
        return f"<{type(self).__name__} id={pk}>"


class TimestampMixin:
    """Cột created_at / updated_at dùng chung.

    Dùng `DATETIME(fsp=6)` của dialect MySQL thay vì `DateTime` chung: DATETIME
    mặc định của MySQL chỉ có độ phân giải 1 giây, khiến nhiều bản ghi tạo trong
    cùng một giây có timestamp giống hệt nhau và không thể sắp xếp ổn định —
    vấn đề thực tế khi crawler ghi hàng loạt job cùng lúc. fsp=6 cho microsecond.
    """

    created_at: Mapped[dt.datetime] = mapped_column(
        DATETIME(fsp=6), default=utcnow, nullable=False, index=True
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DATETIME(fsp=6), default=utcnow, onupdate=utcnow, nullable=False
    )
