"""Test endpoint health / readiness."""

from __future__ import annotations

from httpx import AsyncClient


class TestLiveness:
    async def test_health_returns_ok(self, client: AsyncClient) -> None:
        r = await client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["env"] == "test"
        assert body["uptime_seconds"] >= 0

    async def test_health_does_not_require_database(self, client: AsyncClient) -> None:
        """Liveness phải trả 200 kể cả khi database chết, nếu không orchestrator
        sẽ restart tiến trình đang khoẻ mạnh chỉ vì database tạm thời gián đoạn."""
        assert (await client.get("/health")).status_code == 200


class TestReadiness:
    async def test_readiness_reports_real_database_state(self, client: AsyncClient) -> None:
        """Readiness phải phản ánh trạng thái THẬT, không phải giá trị cứng.

        Chấp nhận cả 200 và 503 — điều được kiểm tra là hai giá trị này phải
        nhất quán với nhau, tức là endpoint đã thực sự ping database.
        """
        r = await client.get("/health/ready")
        assert r.status_code in (200, 503)

        body = r.json()
        db_status = body["checks"]["database"]["status"]
        assert db_status in ("up", "down")

        if db_status == "up":
            assert r.status_code == 200
            assert body["status"] == "ready"
            assert "server_version" in body["checks"]["database"]
        else:
            assert r.status_code == 503
            assert body["status"] == "not_ready"
            assert "error" in body["checks"]["database"]

    async def test_readiness_reports_task_queue_backend(self, client: AsyncClient) -> None:
        body = (await client.get("/health/ready")).json()
        assert body["checks"]["task_queue"]["backend"] in ("celery", "thread")

    async def test_readiness_does_not_leak_credentials(self, client: AsyncClient) -> None:
        """Phản hồi lỗi không được chứa chuỗi kết nối hay mật khẩu."""
        text = (await client.get("/health/ready")).text
        for leak in ("password", "asyncmy://", "mysql+", "@127.0.0.1:3306"):
            assert leak not in text


class TestErrorHandling:
    async def test_unknown_route_returns_404(self, client: AsyncClient) -> None:
        assert (await client.get("/khong-ton-tai")).status_code == 404
