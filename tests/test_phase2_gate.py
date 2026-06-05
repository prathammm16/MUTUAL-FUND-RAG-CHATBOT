"""Phase 2 exit gate — Chroma index + smoke retrieval."""

from pathlib import Path

import pytest

from ingestion.chunk_store import MIN_TOTAL_CHUNKS
from ingestion.index import (
    collection_exists,
    get_indexed_chunk_count,
    query_chunks,
    validate_indexed_store,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VECTOR_STORE = PROJECT_ROOT / "vector_store"


@pytest.fixture(scope="module")
def vector_store_ready():
    pytest.importorskip("chromadb")
    pytest.importorskip("sentence_transformers")
    if not collection_exists(str(VECTOR_STORE)):
        pytest.skip("vector_store missing; run scripts/build_index.py --reset")
    if get_indexed_chunk_count(str(VECTOR_STORE)) < MIN_TOTAL_CHUNKS:
        pytest.skip("index incomplete; run scripts/build_index.py --reset")


class TestPhase2ExitGate:
    def test_collection_exists(self, vector_store_ready) -> None:
        assert collection_exists(str(VECTOR_STORE))

    def test_chunk_count(self, vector_store_ready) -> None:
        assert get_indexed_chunk_count(str(VECTOR_STORE)) >= MIN_TOTAL_CHUNKS

    def test_validate_indexed_store(self, vector_store_ready) -> None:
        errors = validate_indexed_store(str(VECTOR_STORE))
        assert not errors, errors

    def test_smoke_mid_cap_costs(self, vector_store_ready) -> None:
        hits = query_chunks(
            "expense ratio mid cap",
            scheme_id="hdfc-mid-cap",
            min_similarity=0.45,
        )
        assert hits and hits[0].section == "costs"

    def test_smoke_gold_exit_load(self, vector_store_ready) -> None:
        hits = query_chunks(
            "exit load gold etf fof",
            scheme_id="hdfc-gold-etf-fof",
            min_similarity=0.45,
        )
        assert hits and hits[0].section == "exit_load"

    def test_smoke_nifty_manager(self, vector_store_ready) -> None:
        hits = query_chunks(
            "Who manages the HDFC NIFTY 50 Index Fund?",
            scheme_id="hdfc-nifty-50-index",
            min_similarity=0.45,
        )
        assert hits and hits[0].section == "fund_management"
