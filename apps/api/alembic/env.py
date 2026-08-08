"""Môi trường migration của Alembic.

Đọc database URL từ Settings của ứng dụng (tức là từ `.env`) thay vì từ
alembic.ini, để credential không bao giờ nằm trong file được commit.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Cho phép import package `app` khi Alembic chạy từ thư mục apps/api.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
# Alembic chạy đồng bộ nên phải dùng pymysql thay cho asyncmy.
config.set_main_option("sqlalchemy.url", settings.sync_database_url)

target_metadata = Base.metadata


def include_object(
    obj: object, name: str | None, type_: str, reflected: bool, compare_to: object
) -> bool:
    """Bỏ qua các đối tượng do MySQL tự sinh mà Alembic không quản lý.

    MySQL tự tạo index phụ trợ cho FOREIGN KEY. Nếu không loại trừ, autogenerate
    sẽ liên tục sinh ra lệnh drop/create index vô nghĩa.
    """
    return not (type_ == "index" and reflected and compare_to is None)


def run_migrations_offline() -> None:
    """Sinh SQL ra file mà không cần kết nối database."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Chạy migration trực tiếp trên database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=include_object,
            # MySQL DDL không có transaction — mỗi migration phải tự đảm bảo
            # tính đúng đắn khi chạy lại.
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
