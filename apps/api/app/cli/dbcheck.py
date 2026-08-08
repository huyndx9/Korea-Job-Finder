"""Kiểm tra kết nối MySQL và cấu hình charset.

    python -m app.cli.dbcheck

Chạy qua chính engine của ứng dụng chứ không qua `mysql` CLI — như vậy mới xác
nhận được đúng chuỗi kết nối trong `.env` hoạt động, kể cả phần driver và
charset. Kết nối được bằng `mysql` CLI không đảm bảo ứng dụng cũng kết nối được.

Exit code 0 khi mọi thứ đúng, 1 khi có vấn đề — dùng được trong script CI.
"""

from __future__ import annotations

import asyncio
import sys

from app.core.config import get_settings
from app.core.db import check_database_charset, check_database_health, dispose_engine


def _redact(url: str) -> str:
    """Ẩn mật khẩu trong chuỗi kết nối trước khi in ra màn hình."""
    if "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "@" not in rest:
        return url
    credentials, host = rest.rsplit("@", 1)
    user = credentials.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"


async def _run() -> int:
    settings = get_settings()
    print(f"Đang kết nối: {_redact(settings.active_database_url)}")

    health = await check_database_health()
    if health["status"] != "up":
        print(f"FAIL  Không kết nối được MySQL ({health.get('error')})")
        print()
        print("  Kiểm tra lần lượt:")
        print("   1. Service MySQL80 đang chạy?     Get-Service MySQL80")
        print("   2. Đã tạo database chưa?          .\\make.ps1 db-setup")
        print("   3. DATABASE_URL trong .env đúng chưa?")
        await dispose_engine()
        return 1

    print(f"OK    MySQL {health['server_version']}")

    charset = await check_database_charset()
    if charset["status"] == "ok":
        print(f"OK    charset {charset['charset']} / {charset['collation']}")
        exit_code = 0
    else:
        # Charset sai là lỗi âm thầm nguy hiểm: dữ liệu ghi vào vẫn "thành công"
        # nhưng tiếng Hàn và tiếng Việt có dấu bị biến dạng vĩnh viễn.
        print(f"FAIL  charset {charset.get('charset')} — bắt buộc phải là utf8mb4")
        print("      Tiếng Hàn và tiếng Việt có dấu sẽ bị hỏng.")
        print("      Sửa: ALTER DATABASE vietjob CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        exit_code = 1

    await dispose_engine()
    return exit_code


def main() -> None:
    sys.exit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
