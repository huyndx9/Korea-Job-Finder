"""Test fixtures.

The DB path is set through the environment *before* app.config is imported, so
every test run gets its own throwaway SQLite file and never touches the dev one.
No test is allowed to hit the network: collectors are always faked.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

TEST_DB = Path(tempfile.gettempdir()) / "korea_job_finder_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["DEMO_MODE"] = "false"
os.environ["SARAMIN_API_KEY"] = ""
os.environ["WORK24_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    """Every test starts from an empty schema and no remembered source health."""
    from app.services import source_status

    source_status.reset()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


# ------------------------------------------------------------ fake HTTP layer


class FakeResponse:
    def __init__(self, text: str = "", json_data: object = None, status_code: int = 200) -> None:
        self.text = text
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> object:
        return self._json


class FakeClient:
    """Stand-in for httpx.Client - same context-manager + .get() surface."""

    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, dict]] = []

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def get(self, url: str, params: dict | None = None, **_kwargs: object) -> FakeResponse:
        self.calls.append((url, params or {}))
        return self.response


@pytest.fixture
def fake_http(monkeypatch):
    """Point every collector's HTTP client at a canned response."""

    def _install(response: FakeResponse) -> FakeClient:
        fake = FakeClient(response)
        from app.collectors.base import JobCollector

        monkeypatch.setattr(JobCollector, "_client", lambda self: fake)
        return fake

    return _install
