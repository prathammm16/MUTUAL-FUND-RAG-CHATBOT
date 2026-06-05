"""Phase 2 — Chroma index tests; Phase 7 daily pipeline in ``test_phase7_daily.py``."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.config import get_all_schemes
from ingestion.chunk import Chunk, chunk_scheme
from ingestion.chunk_store import MIN_TOTAL_CHUNKS
from ingestion.index import (
    COLLECTION_NAME,
    DEFAULT_INDEX_DIR,
    RetrievedChunk,
    chunk_to_metadata,
    collection_exists,
    distance_to_similarity,
    get_indexed_chunk_count,
    query_chunks,
    upsert_chunks,
    validate_indexed_store,
)
from ingestion.parse import parse_document

SAMPLE = Path(__file__).parent / "fixtures" / "sample_mid_cap.md"
MID_CAP_URL = "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"


@pytest.fixture
def sample_chunks():
    raw = SAMPLE.read_text(encoding="utf-8")
    parsed = parse_document(raw, scheme_id="hdfc-mid-cap")
    return chunk_scheme(parsed)


class TestIndexHelpers:
    def test_distance_to_similarity(self) -> None:
        assert distance_to_similarity(0.0) == 1.0
        assert distance_to_similarity(0.2) == pytest.approx(0.8)

    def test_chunk_to_metadata_ingested_at(self, sample_chunks) -> None:
        meta = chunk_to_metadata(sample_chunks[0], ingested_at="2026-06-05")
        assert meta["ingested_at"] == "2026-06-05"
        assert meta["scheme_id"] == "hdfc-mid-cap"
        assert meta["source_url"] == MID_CAP_URL


class TestUpsertChunks:
    def test_upsert_calls_collection(self, sample_chunks) -> None:
        collection = MagicMock()
        embeddings = [[0.1] * 8 for _ in sample_chunks]
        n = upsert_chunks(collection, sample_chunks, embeddings, ingested_at="2026-06-05")
        assert n == len(sample_chunks)
        collection.upsert.assert_called_once()
        call = collection.upsert.call_args.kwargs
        assert call["ids"][0] == sample_chunks[0].chunk_id
        assert call["metadatas"][0]["ingested_at"] == "2026-06-05"


class TestValidateIndexedStore:
    def test_missing_collection_returns_error(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("VECTOR_STORE_PATH", str(tmp_path / "empty"))
        from app.config import get_settings

        get_settings.cache_clear()
        errors = validate_indexed_store(str(tmp_path / "empty"))
        get_settings.cache_clear()
        assert errors
        assert "not found" in errors[0].lower()


@pytest.mark.integration
class TestPhase2Integration:
    """Requires ``pip install -r requirements.txt`` and ``python scripts/build_index.py``."""

    @pytest.fixture(scope="class")
    def ensure_index(self):
        pytest.importorskip("chromadb")
        from tests.conftest import require_local_embeddings

        require_local_embeddings()
        from ingestion.index import index_corpus

        root = Path(__file__).resolve().parents[1]
        index_dir = str(DEFAULT_INDEX_DIR)
        if not collection_exists(index_dir):
            index_corpus(persist_directory=index_dir, reset_collection=True)
        elif get_indexed_chunk_count(index_dir) < MIN_TOTAL_CHUNKS:
            index_corpus(persist_directory=index_dir, reset_collection=True)

    def test_index_has_minimum_chunks(self, ensure_index) -> None:
        count = get_indexed_chunk_count(str(DEFAULT_INDEX_DIR))
        assert count >= MIN_TOTAL_CHUNKS

    def test_validate_indexed_store_passes(self, ensure_index) -> None:
        errors = validate_indexed_store(str(DEFAULT_INDEX_DIR))
        assert not errors, errors

    def test_mid_cap_expense_ratio_retrieval(self, ensure_index) -> None:
        hits = query_chunks(
            "expense ratio HDFC Mid Cap Fund",
            scheme_id="hdfc-mid-cap",
            min_similarity=0.45,
        )
        assert hits
        assert hits[0].scheme_id == "hdfc-mid-cap"
        assert hits[0].section == "costs"

    def test_gold_exit_load_retrieval(self, ensure_index) -> None:
        hits = query_chunks(
            "exit load gold ETF fund of fund",
            scheme_id="hdfc-gold-etf-fof",
            min_similarity=0.45,
        )
        assert hits
        assert hits[0].scheme_id == "hdfc-gold-etf-fof"
        assert hits[0].section == "exit_load"

    def test_nifty_manager_retrieval(self, ensure_index) -> None:
        hits = query_chunks(
            "Who manages the HDFC NIFTY 50 Index Fund?",
            scheme_id="hdfc-nifty-50-index",
            min_similarity=0.45,
        )
        assert hits
        assert hits[0].scheme_id == "hdfc-nifty-50-index"
        assert hits[0].section == "fund_management"

    def test_all_five_schemes_represented(self, ensure_index) -> None:
        from ingestion.index import get_collection

        collection = get_collection(str(DEFAULT_INDEX_DIR))
        data = collection.get(include=["metadatas"])
        found = {m["scheme_id"] for m in data["metadatas"] if m}
        expected = {s.scheme_id for s in get_all_schemes()}
        assert expected == found


# PH7-02 / RT-09 — stable per-scheme retrieval thresholds (no flaky 0.99 cutoffs)
STABLE_MIN_SIMILARITY = 0.45

SCHEME_RETRIEVAL_GOLDEN = [
    (
        "hdfc-silver-etf-fof",
        "expense ratio HDFC Silver ETF FoF",
        "costs",
        "0.21",
    ),
    (
        "hdfc-mid-cap",
        "expense ratio HDFC Mid Cap Fund",
        "costs",
        "0.73",
    ),
    (
        "hdfc-equity",
        "expense ratio HDFC Equity Fund",
        "costs",
        "0.68",
    ),
    (
        "hdfc-gold-etf-fof",
        "exit load gold ETF fund of fund",
        "exit_load",
        "1%",
    ),
    (
        "hdfc-nifty-50-index",
        "Who manages the HDFC NIFTY 50 Index Fund?",
        "fund_management",
        "manager",
    ),
]


@pytest.mark.integration
class TestPhase9PerSchemeRetrieval:
    """RT-09 — each scheme retrieves the correct section and fact at stable threshold."""

    @pytest.fixture(scope="class")
    def ensure_index(self):
        pytest.importorskip("chromadb")
        from tests.conftest import require_local_embeddings

        require_local_embeddings()
        from ingestion.index import index_corpus

        index_dir = str(DEFAULT_INDEX_DIR)
        if not collection_exists(index_dir):
            index_corpus(persist_directory=index_dir, reset_collection=True)
        elif get_indexed_chunk_count(index_dir) < MIN_TOTAL_CHUNKS:
            index_corpus(persist_directory=index_dir, reset_collection=True)

    @pytest.mark.parametrize(
        "scheme_id,query,section,snippet",
        SCHEME_RETRIEVAL_GOLDEN,
        ids=[row[0] for row in SCHEME_RETRIEVAL_GOLDEN],
    )
    def test_rt09_scheme_specific_hit(
        self,
        ensure_index,
        scheme_id: str,
        query: str,
        section: str,
        snippet: str,
    ) -> None:
        hits = query_chunks(
            query,
            scheme_id=scheme_id,
            min_similarity=STABLE_MIN_SIMILARITY,
        )
        assert hits, f"no hits for {scheme_id}: {query}"
        assert hits[0].scheme_id == scheme_id
        assert hits[0].section == section
        content = hits[0].document.lower()
        assert snippet.lower() in content


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: tests that build/query Chroma + sentence-transformers",
    )
