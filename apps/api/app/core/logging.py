"""Structured logging.

Bảo vệ dữ liệu nhạy cảm được thực hiện bằng một structlog processor
(`redact_sensitive`) chạy trên MỌI log event, thay vì dựa vào kỷ luật của
người viết code. Nếu ai đó lỡ log `password=...` thì giá trị vẫn bị che.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

from app.core.config import LogFormat, Settings

REDACTED = "***REDACTED***"

# So khớp theo cách "tên khoá có chứa chuỗi này" (không phân biệt hoa thường).
SENSITIVE_KEY_PATTERNS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "auth",
        "cookie",
        "session",
        "credential",
        "private_key",
        # Dữ liệu cá nhân / nội dung CV
        "resume_text",
        "parsed_text",
        "cv_text",
        "email",
        "phone",
        "address",
        "ssn",
        "national_id",
        "passport",
    }
)


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(pattern in lowered for pattern in SENSITIVE_KEY_PATTERNS)


def _redact_value(value: Any, depth: int = 0) -> Any:
    """Che đệ quy các khoá nhạy cảm trong dict/list lồng nhau."""
    if depth > 6:  # chặn cấu trúc quá sâu hoặc tự tham chiếu
        return value
    if isinstance(value, MutableMapping):
        return {
            k: (REDACTED if _is_sensitive(str(k)) else _redact_value(v, depth + 1))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_value(v, depth + 1) for v in value]
    return value


def redact_sensitive(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Structlog processor: che secret và PII trước khi ghi ra bất kỳ sink nào."""
    for key in list(event_dict.keys()):
        if _is_sensitive(str(key)):
            event_dict[key] = REDACTED
        else:
            event_dict[key] = _redact_value(event_dict[key])
    return event_dict


def configure_logging(settings: Settings) -> None:
    """Cấu hình structlog + stdlib logging. Gọi đúng một lần lúc khởi động."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level, force=True)

    # Thư viện bên thứ ba quá ồn ở mức INFO.
    for noisy in ("asyncmy", "aiomysql", "httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    renderer: Any = (
        structlog.processors.JSONRenderer()
        if settings.log_format is LogFormat.json
        else structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_sensitive,  # phải chạy TRƯỚC renderer
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """Trả về structlog logger đã gắn tên module."""
    return structlog.get_logger(name)
