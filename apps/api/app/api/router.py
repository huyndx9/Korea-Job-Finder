"""Điểm gắn kết mọi router của API.

Router con được include ở đây theo từng phase.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import health

api_router = APIRouter()

# Health nằm ngoài prefix /api để load balancer / uptime monitor gọi dễ.
api_router.include_router(health.router)
