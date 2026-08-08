"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.db import dispose_engine
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    log.info(
        "app_starting",
        env=settings.app_env.value,
        single_user_mode=settings.single_user_mode,
        ai_provider=settings.ai_provider.value,
        task_queue="celery" if settings.use_celery else "thread",
    )
    if settings.single_user_mode:
        log.warning(
            "single_user_mode_active",
            detail=(
                "Authentication đang tắt. Server chỉ bind loopback. "
                "Không deploy cấu hình này ra ngoài."
            ),
        )
    yield
    await dispose_engine()
    log.info("app_stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "Nền tảng tổng hợp việc làm và AI matching cho người Việt tìm việc tại Hàn Quốc."
        ),
        lifespan=lifespan,
        # Ẩn tài liệu API ở production.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        """Dịch exception của domain thành HTTP response.

        Đây là nơi DUY NHẤT ánh xạ lỗi domain sang HTTP.
        """
        log.warning("app_error", code=exc.code, message=exc.message, details=exc.details)
        return JSONResponse(status_code=exc.status_code, content={"error": exc.to_payload()})

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
        """Không bao giờ để lộ nội dung exception ra client ở production."""
        log.exception("unhandled_error", error_type=type(exc).__name__)
        message = str(exc) if settings.app_debug else "Đã xảy ra lỗi không mong muốn."
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": message}},
        )

    app.include_router(api_router)
    return app


app = create_app()
