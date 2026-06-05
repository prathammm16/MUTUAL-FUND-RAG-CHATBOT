"""Phase 7 — daily ingestion pipeline, lock, and atomic swap."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from ingestion.pipeline_state import (
    DEFAULT_INGEST_STATE_DIR,
    IngestLockError,
    IngestStatus,
    acquire_ingest_lock,
    is_ingesting,
    read_ingest_status,
    release_ingest_lock,
    write_ingest_status,
)
from ingestion.run_daily import (
    DailyIngestError,
    atomic_swap_index,
    check_chunk_count_drop,
    run_daily_ingest,
)


@pytest.fixture
def isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = tmp_path / "vector_store"
    state = tmp_path / "ingest"
    monkeypatch.setenv("VECTOR_STORE_PATH", str(store))
    monkeypatch.setattr(
        "ingestion.pipeline_state.DEFAULT_INGEST_STATE_DIR",
        state,
    )
    monkeypatch.setattr(
        "ingestion.run_daily.DEFAULT_INGEST_STATE_DIR",
        state,
    )
    get_settings.cache_clear()
    yield store
    get_settings.cache_clear()


class TestPipelineState:
    def test_lock_prevents_overlap(self, tmp_path: Path) -> None:
        state = tmp_path / "ingest"
        acquire_ingest_lock(state, ttl_sec=3600)
        with pytest.raises(IngestLockError):
            acquire_ingest_lock(state, ttl_sec=3600)
        release_ingest_lock(state)

    def test_stale_lock_removed(self, tmp_path: Path) -> None:
        state = tmp_path / "ingest"
        state.mkdir(parents=True)
        lock = state / ".ingest.lock"
        lock.write_text("{}", encoding="utf-8")
        old = time.time() - 10_000
        import os

        os.utime(lock, (old, old))
        acquire_ingest_lock(state, ttl_sec=60)
        release_ingest_lock(state)

    def test_ingesting_flag(self, tmp_path: Path) -> None:
        state = tmp_path / "ingest"
        write_ingest_status(
            IngestStatus(ingesting=True, started_at="t0"),
            state,
        )
        assert is_ingesting(state)
        write_ingest_status(IngestStatus(ingesting=False), state)
        assert not is_ingesting(state)


class TestAtomicSwap:
    def test_swap_promotes_staging(self, tmp_path: Path) -> None:
        live = tmp_path / "live"
        staging = tmp_path / "live.staging"
        live.mkdir()
        (live / "old.txt").write_text("old", encoding="utf-8")
        staging.mkdir()
        (staging / "marker.txt").write_text("new", encoding="utf-8")
        atomic_swap_index(staging, live)
        assert live.is_dir()
        assert (live / "marker.txt").read_text() == "new"
        assert not staging.exists()
        prev = tmp_path / "live.previous"
        assert prev.is_dir()
        assert (prev / "old.txt").read_text() == "old"


class TestChunkDropGuard:
    def test_rejects_large_drop(self) -> None:
        with pytest.raises(DailyIngestError, match="PH7-03"):
            check_chunk_count_drop(10, 100, max_drop_ratio=0.5)

    def test_allows_small_drop(self) -> None:
        check_chunk_count_drop(80, 100, max_drop_ratio=0.5)


@pytest.mark.integration
class TestRunDailyOffline:
    """Uses committed corpus/raw; builds index in isolated store."""

    def test_run_daily_skip_fetch(self, isolated_store: Path) -> None:
        pytest.importorskip("chromadb")
        from tests.conftest import require_local_embeddings

        require_local_embeddings()
        result = run_daily_ingest(skip_fetch=True, live_index_dir=isolated_store)
        assert result.chunk_count >= 40
        assert result.ingested_at
        errors = __import__(
            "ingestion.index", fromlist=["validate_indexed_store"]
        ).validate_indexed_store(str(isolated_store))
        assert not errors, errors

    def test_second_run_updates_metadata(self, isolated_store: Path) -> None:
        pytest.importorskip("chromadb")
        from tests.conftest import require_local_embeddings

        require_local_embeddings()
        from ingestion.index import close_chroma_clients

        first = run_daily_ingest(skip_fetch=True, live_index_dir=isolated_store)
        close_chroma_clients()
        time.sleep(0.5)
        second = run_daily_ingest(skip_fetch=True, live_index_dir=isolated_store)
        assert second.chunk_count == first.chunk_count
        status = read_ingest_status()
        assert status.last_success_at
        assert not status.last_error


class TestHealthIngesting:
    def test_health_reports_ingesting(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "app.api.routes.is_ingesting",
            lambda store_dir=None: True,
        )
        monkeypatch.setattr(
            "app.api.routes.read_ingest_status",
            lambda store_dir=None: IngestStatus(
                ingesting=True,
                last_error="test run",
            ),
        )
        client = TestClient(create_app())
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ingesting"] is True
        assert body["last_ingest_error"] == "test run"


class TestAdminReindex:
    def test_admin_disabled_without_token(self, isolated_store: Path) -> None:
        client = TestClient(create_app())
        resp = client.post("/api/admin/reindex", headers={"X-Admin-Token": "x"})
        assert resp.status_code == 404

    def test_admin_reindex_with_token(self, isolated_store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pytest.importorskip("chromadb")
        from tests.conftest import require_local_embeddings

        require_local_embeddings()
        monkeypatch.setenv("ADMIN_REINDEX_TOKEN", "test-secret")
        get_settings.cache_clear()
        client = TestClient(create_app())
        resp = client.post(
            "/api/admin/reindex",
            headers={"X-Admin-Token": "test-secret"},
        )
        get_settings.cache_clear()
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["chunk_count"] >= 40
