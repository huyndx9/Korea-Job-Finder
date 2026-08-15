"""Live per-source health, as reported by /api/sources.

In-memory only: it describes what this process has seen since it started, which
is exactly what the UI needs ("is Saramin actually talking to us right now?").
Nothing here is persisted.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from app.collectors.base import SourceStatus


@dataclass
class SourceState:
    status: SourceStatus
    message: str | None = None
    last_success: str | None = None      # ISO-8601, last time the source returned data
    last_result_count: int = 0
    last_checked: str | None = None


_lock = threading.Lock()
_state: dict[str, SourceState] = {}


def record(source: str, status: SourceStatus, message: str | None, count: int) -> None:
    """Remember the outcome of one collector run."""
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        current = _state.get(source)
        last_success = current.last_success if current else None
        if status in (SourceStatus.CONNECTED, SourceStatus.DEMO) and count > 0:
            last_success = now
        _state[source] = SourceState(
            status=status,
            message=message,
            last_success=last_success,
            last_result_count=count,
            last_checked=now,
        )


def get(source: str) -> SourceState | None:
    with _lock:
        return _state.get(source)


def reset() -> None:
    """Test helper - forget everything this process has observed."""
    with _lock:
        _state.clear()
