"""Phân cấp exception của ứng dụng + ánh xạ sang HTTP response.

`services/` và `repositories/` ném các exception trong file này. Tầng `api/`
là nơi DUY NHẤT dịch chúng thành HTTP status — nhờ vậy business logic không
phải import FastAPI.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Gốc của mọi lỗi do ứng dụng chủ động sinh ra."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "permission_denied"


class AuthenticationRequiredError(AppError):
    status_code = 401
    code = "authentication_required"


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"


# ---------------------------------------------------------------------------
# Lỗi hạ tầng
# ---------------------------------------------------------------------------


class DatabaseUnavailableError(AppError):
    status_code = 503
    code = "database_unavailable"


class AIUnavailableError(AppError):
    """AI provider chưa cấu hình, hết hạn chờ, hoặc không phản hồi.

    KHÔNG được nuốt lỗi này để trả về kết quả giả. Caller phải đánh dấu bản ghi
    là `AI_ANALYSIS_PENDING` và thử lại sau.
    """

    status_code = 503
    code = "ai_unavailable"


class AIOutputInvalidError(AppError):
    """LLM trả về output không khớp schema sau khi đã retry hết số lần cho phép."""

    status_code = 502
    code = "ai_output_invalid"


class SourceUnavailableError(AppError):
    """Một job source không truy cập được. Không được làm dừng các source khác."""

    status_code = 503
    code = "source_unavailable"


class SourceDisabledError(AppError):
    """Source bị tắt có chủ đích (thiếu API key, hoặc ToS không cho phép thu thập)."""

    status_code = 409
    code = "source_disabled"


class UnsupportedFileTypeError(AppError):
    status_code = 415
    code = "unsupported_file_type"


class FileTooLargeError(AppError):
    status_code = 413
    code = "file_too_large"
