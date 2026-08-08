"""Test các bất biến an toàn của cấu hình.

Đây là những kiểm tra ngăn một lỗi cấu hình biến thành sự cố lộ dữ liệu, nên
chúng phải được test tường minh.
"""

from __future__ import annotations

import pytest

from app.core.config import AppEnv, ConfigurationError, Settings

BASE: dict[str, object] = {
    "database_url": "mysql+asyncmy://u:p@127.0.0.1:3306/vietjob?charset=utf8mb4",
    "test_database_url": "mysql+asyncmy://u:p@127.0.0.1:3306/vietjob_test?charset=utf8mb4",
}


def make(**overrides: object) -> Settings:
    return Settings(**{**BASE, **overrides})  # type: ignore[arg-type]


class TestSafetyInvariants:
    def test_single_user_mode_rejected_in_production(self) -> None:
        with pytest.raises(ConfigurationError, match="SINGLE_USER_MODE"):
            make(app_env=AppEnv.production, single_user_mode=True)

    def test_production_with_auth_is_allowed(self) -> None:
        s = make(
            app_env=AppEnv.production,
            single_user_mode=False,
            api_host="0.0.0.0",
            app_debug=False,
        )
        assert s.is_production

    def test_single_user_mode_must_bind_loopback(self) -> None:
        with pytest.raises(ConfigurationError, match="loopback"):
            make(single_user_mode=True, api_host="0.0.0.0")

    @pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
    def test_single_user_mode_accepts_loopback_forms(self, host: str) -> None:
        assert make(single_user_mode=True, api_host=host).api_host == host

    def test_external_bind_allowed_only_with_explicit_optin(self) -> None:
        """Chạy trong container cần bind 0.0.0.0, nhưng phải là lựa chọn có ý thức."""
        s = make(single_user_mode=True, api_host="0.0.0.0", single_user_allow_external_bind=True)
        assert s.api_host == "0.0.0.0"

    def test_external_bind_optin_does_not_unlock_production(self) -> None:
        """Cờ này chỉ nới lỏng ràng buộc bind, không được phép mở đường cho
        single-user mode chạy ở production."""
        with pytest.raises(ConfigurationError, match="SINGLE_USER_MODE"):
            make(
                app_env=AppEnv.production,
                single_user_mode=True,
                api_host="0.0.0.0",
                single_user_allow_external_bind=True,
            )

    def test_debug_rejected_in_production(self) -> None:
        with pytest.raises(ConfigurationError, match="APP_DEBUG"):
            make(app_env=AppEnv.production, single_user_mode=False, app_debug=True)

    def test_test_db_must_differ_from_main_db(self) -> None:
        same = "mysql+asyncmy://u:p@127.0.0.1:3306/vietjob?charset=utf8mb4"
        with pytest.raises(ConfigurationError, match="cùng một database"):
            make(database_url=same, test_database_url=same)

    def test_non_mysql_url_rejected(self) -> None:
        with pytest.raises(ConfigurationError, match="chỉ hỗ trợ MySQL"):
            make(database_url="postgresql+asyncpg://u:p@localhost/vietjob")


class TestDerivedProperties:
    def test_cors_origins_parsed_from_csv(self) -> None:
        s = make(cors_origins="http://a.test, http://b.test ,, http://c.test")
        assert s.cors_origin_list == ["http://a.test", "http://b.test", "http://c.test"]

    def test_sync_url_swaps_async_driver_for_alembic(self) -> None:
        s = make(app_env=AppEnv.development)
        assert s.sync_database_url.startswith("mysql+pymysql://")
        assert "asyncmy" not in s.sync_database_url

    def test_active_url_switches_to_test_db_under_test_env(self) -> None:
        s = make(app_env=AppEnv.test)
        assert s.active_database_url.endswith("vietjob_test?charset=utf8mb4")

    def test_active_url_uses_main_db_outside_test_env(self) -> None:
        s = make(app_env=AppEnv.development)
        assert s.active_database_url.endswith("vietjob?charset=utf8mb4")

    def test_celery_disabled_without_redis(self) -> None:
        assert make(redis_url="").use_celery is False
        assert make(redis_url="  ").use_celery is False

    def test_celery_enabled_with_redis(self) -> None:
        assert make(redis_url="redis://localhost:6379/0").use_celery is True

    def test_resume_dir_is_absolute(self) -> None:
        assert make().resume_dir.is_absolute()


class TestSecretHandling:
    def test_api_keys_are_not_exposed_by_repr(self) -> None:
        """SecretStr đảm bảo key không lọt vào log hay traceback."""
        s = make(anthropic_api_key="sk-ant-super-secret")
        assert "sk-ant-super-secret" not in repr(s)
        assert "sk-ant-super-secret" not in str(s.anthropic_api_key)
        assert s.anthropic_api_key.get_secret_value() == "sk-ant-super-secret"
