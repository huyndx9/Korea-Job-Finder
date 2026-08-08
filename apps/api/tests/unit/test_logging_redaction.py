"""Test lớp bảo vệ dữ liệu nhạy cảm trong log.

Đây là biện pháp kiểm soát an toàn, không phải tiện ích — nếu nó hỏng thì
secret và dữ liệu CV sẽ rò ra file log. Vì vậy phải test kỹ.
"""

from __future__ import annotations

import pytest

from app.core.logging import REDACTED, redact_sensitive


def redact(**event: object) -> dict[str, object]:
    return dict(redact_sensitive(None, "info", event))


class TestTopLevelRedaction:
    @pytest.mark.parametrize(
        "key",
        [
            "password",
            "Password",
            "PASSWORD",
            "db_password",
            "api_key",
            "apikey",
            "ANTHROPIC_API_KEY",
            "access_token",
            "refresh_token",
            "authorization",
            "cookie",
            "session_id",
            "credential",
            "private_key",
            "secret",
        ],
    )
    def test_secret_keys_are_redacted(self, key: str) -> None:
        assert redact(**{key: "leak-me"})[key] == REDACTED

    @pytest.mark.parametrize(
        "key",
        ["email", "phone", "address", "ssn", "passport", "parsed_text", "resume_text", "cv_text"],
    )
    def test_personal_data_keys_are_redacted(self, key: str) -> None:
        assert redact(**{key: "sensitive"})[key] == REDACTED

    def test_ordinary_keys_pass_through(self) -> None:
        out = redact(event="crawler_run", source="saramin", jobs_found=42, duration_ms=1234)
        assert out == {
            "event": "crawler_run",
            "source": "saramin",
            "jobs_found": 42,
            "duration_ms": 1234,
        }


class TestNestedRedaction:
    def test_nested_dict_is_redacted(self) -> None:
        out = redact(config={"db": {"host": "localhost", "password": "hunter2"}})
        assert out["config"] == {"db": {"host": "localhost", "password": REDACTED}}

    def test_list_of_dicts_is_redacted(self) -> None:
        out = redact(users=[{"name": "A", "email": "a@x.test"}, {"name": "B", "email": "b@x.test"}])
        assert out["users"] == [
            {"name": "A", "email": REDACTED},
            {"name": "B", "email": REDACTED},
        ]

    def test_deeply_nested_secret_is_redacted(self) -> None:
        out = redact(a={"b": {"c": {"d": {"api_key": "sk-leak"}}}})
        assert out["a"]["b"]["c"]["d"]["api_key"] == REDACTED  # type: ignore[index]


class TestRobustness:
    def test_does_not_crash_on_none_or_scalars(self) -> None:
        out = redact(a=None, b=1, c=1.5, d=True, e=b"bytes")
        assert out["a"] is None
        assert out["b"] == 1

    def test_self_referencing_structure_does_not_hang(self) -> None:
        """Cấu trúc tự tham chiếu phải dừng nhờ giới hạn độ sâu, không treo vô hạn."""
        loop: dict[str, object] = {"name": "x"}
        loop["self"] = loop
        redact(payload=loop)  # không được raise, không được treo
