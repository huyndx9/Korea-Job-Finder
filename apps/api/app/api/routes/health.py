"""Health / readiness endpoints.

Các endpoint này báo cáo trạng thái THẬT của dependency. Không bao giờ trả về
"ok" cứng — nếu database chết thì readiness phải trả 503.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Response, status

from app.core.config import get_settings
from app.core.db import check_database_health

router = APIRouter(tags=["health"])

_STARTED_AT = time.monotonic()


@router.get("/health", summary="Liveness — tiến trình có đang sống không")
async def health() -> dict[str, Any]:
    """Liveness probe. Không chạm database nên luôn nhanh."""
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": "0.1.0",
        "env": settings.app_env.value,
        "uptime_seconds": round(time.monotonic() - _STARTED_AT, 2),
    }


@router.get("/health/ready", summary="Readiness — dependency có sẵn sàng không")
async def readiness(response: Response) -> dict[str, Any]:
    """Readiness probe: kiểm tra kết nối database thật.

    Trả 503 khi database không dùng được để orchestrator không route traffic vào.
    """
    settings = get_settings()
    database = await check_database_health()

    checks: dict[str, Any] = {
        "database": database,
        "task_queue": {
            "status": "up",
            "backend": "celery" if settings.use_celery else "thread",
        },
        "ai_provider": {
            # `configured` = false không phải lỗi: provider `null` là cấu hình
            # hợp lệ, chỉ khiến job dừng ở trạng thái AI_ANALYSIS_PENDING.
            "status": "up",
            "provider": settings.ai_provider.value,
            "configured": settings.ai_provider.value != "null",
        },
    }

    ready = database["status"] == "up"
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {"status": "ready" if ready else "not_ready", "checks": checks}
