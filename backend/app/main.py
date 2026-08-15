"""FastAPI entrypoint. Creates the SQLite file on first boot."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import custom_sources_router, router
from app.config import settings
from app.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("%s ready | db=%s | demo_mode=%s", settings.app_name, settings.database_url, settings.demo_mode)
    yield


app = FastAPI(
    title=settings.app_name,
    description="여러 한국 채용 사이트를 한 번에 검색하는 잡 애그리게이터",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# the more specific /api/sources/custom routes must win over /api/sources
app.include_router(custom_sources_router)
app.include_router(router)


@app.get("/")
def root() -> dict[str, str]:
    return {"app": settings.app_name, "docs": "/docs", "api": "/api/health"}
