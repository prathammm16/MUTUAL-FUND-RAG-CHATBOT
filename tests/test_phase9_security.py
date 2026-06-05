"""Phase 9 — production API hardening (rate limit, CORS, admin lockdown)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from app.middleware.rate_limit import reset_chat_rate_limiter


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    reset_chat_rate_limiter()
    yield
    get_settings.cache_clear()
    reset_chat_rate_limiter()


@pytest.fixture
def prod_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CHAT_RATE_LIMIT_PER_MINUTE", "3")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("ADMIN_REINDEX_ENABLED", "false")
    monkeypatch.setenv("ADMIN_REINDEX_TOKEN", "")
    get_settings.cache_clear()
    reset_chat_rate_limiter()
    client = TestClient(create_app())
    yield client
    get_settings.cache_clear()
    reset_chat_rate_limiter()


class TestRateLimit:
    def test_ap04_chat_burst_returns_429(self, prod_client: TestClient) -> None:
        payload = {"message": "Which fund is better?"}
        for _ in range(3):
            resp = prod_client.post("/api/chat", json=payload)
            assert resp.status_code == 200
        resp = prod_client.post("/api/chat", json=payload)
        assert resp.status_code == 429
        assert "rate limit" in resp.json()["detail"].lower()

    def test_se01_rate_limit_only_on_chat(self, prod_client: TestClient) -> None:
        for _ in range(5):
            assert prod_client.get("/api/health").status_code == 200
            assert prod_client.get("/api/schemes").status_code == 200

    def test_se02_max_length_still_422(self, prod_client: TestClient) -> None:
        resp = prod_client.post("/api/chat", json={"message": "x" * 4097})
        assert resp.status_code == 422

    def test_dev_mode_no_rate_limit_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("CHAT_RATE_LIMIT_PER_MINUTE", "0")
        get_settings.cache_clear()
        reset_chat_rate_limiter()
        client = TestClient(create_app())
        payload = {"message": "Which fund is better?"}
        for _ in range(5):
            assert client.post("/api/chat", json=payload).status_code == 200


class TestAdminLockdown:
    def test_ap08_admin_disabled_in_production(self, prod_client: TestClient) -> None:
        resp = prod_client.post(
            "/api/admin/reindex",
            headers={"X-Admin-Token": "anything"},
        )
        assert resp.status_code == 404

    def test_admin_disabled_when_flag_off(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("ADMIN_REINDEX_ENABLED", "false")
        monkeypatch.setenv("ADMIN_REINDEX_TOKEN", "secret")
        get_settings.cache_clear()
        client = TestClient(create_app())
        resp = client.post(
            "/api/admin/reindex",
            headers={"X-Admin-Token": "secret"},
        )
        assert resp.status_code == 404

    def test_admin_401_wrong_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("ADMIN_REINDEX_ENABLED", "true")
        monkeypatch.setenv("ADMIN_REINDEX_TOKEN", "good-token")
        get_settings.cache_clear()
        client = TestClient(create_app())
        resp = client.post(
            "/api/admin/reindex",
            headers={"X-Admin-Token": "bad-token"},
        )
        assert resp.status_code == 401


class TestProdCors:
    def test_cors_origins_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("CORS_ORIGINS", "https://ui.example.com,https://www.example.com")
        monkeypatch.setenv("CHAT_RATE_LIMIT_PER_MINUTE", "0")
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.resolved_cors_origins() == [
            "https://ui.example.com",
            "https://www.example.com",
        ]

    def test_prod_default_cors_same_origin_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("CORS_ORIGINS", "")
        monkeypatch.setenv("SERVE_UI", "true")
        get_settings.cache_clear()
        origins = get_settings().resolved_cors_origins()
        assert "http://localhost:8000" in origins
        assert "http://localhost:5173" not in origins
        assert get_settings().resolved_cors_origin_regex() is None

    def test_prod_split_deploy_allows_vercel_regex(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("SERVE_UI", "false")
        monkeypatch.setenv("CORS_ORIGINS", "")
        get_settings.cache_clear()
        assert get_settings().resolved_cors_origin_regex() == r"https://.*\.vercel\.app"
