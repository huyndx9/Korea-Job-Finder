"""SQLAlchemy models.

Mọi model PHẢI được import ở đây. Alembic autogenerate chỉ nhìn thấy các bảng
đã đăng ký vào `Base.metadata`; model không import ở đây sẽ bị coi là đã bị xoá
và Alembic sẽ sinh migration DROP TABLE.
"""

from __future__ import annotations

from app.models.base import Base, TimestampMixin, Vector, utcnow

__all__ = ["Base", "TimestampMixin", "Vector", "utcnow"]
