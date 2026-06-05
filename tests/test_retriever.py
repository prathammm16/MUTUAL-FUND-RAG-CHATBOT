"""Phase 4 — retriever, scheme filter, section boost, context assembly."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import get_all_schemes, resolve_scheme_id_from_text
from app.rag.retriever import (
    NOT_FOUND_MESSAGE,
    build_context,
    document_to_content,
    effective_min_similarity,
    infer_section_hint,
    query_implies_all_schemes,
    retrieve,
)
from ingestion.index import collection_exists

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VECTOR_STORE = str(PROJECT_ROOT / "vector_store")


@pytest.fixture(scope="module")
def vector_store_ready():
    pytest.importorskip("chromadb")
    from tests.conftest import require_local_embeddings

    require_local_embeddings()
    if not collection_exists(VECTOR_STORE):
        pytest.skip("vector_store missing; run scripts/build_index.py --reset")


class TestRetrieverHelpers:
    def test_sc02_silver_alias(self) -> None:
        assert resolve_scheme_id_from_text("min SIP for silver fund") == "hdfc-silver-etf-fof"

    def test_sc04_nifty_alias(self) -> None:
        assert resolve_scheme_id_from_text("Nifty 50 index expense") == "hdfc-nifty-50-index"

    def test_infer_manager_section(self) -> None:
        assert infer_section_hint("Who manages the HDFC NIFTY 50 Index Fund?") == "fund_management"

    def test_infer_costs_section(self) -> None:
        assert infer_section_hint("What is the expense ratio?") == "costs"

    def test_all_schemes_phrase(self) -> None:
        assert query_implies_all_schemes("minimum SIP for all five schemes")

    def test_effective_threshold_local_filtered(self) -> None:
        assert effective_min_similarity(scheme_id="hdfc-mid-cap") == 0.60

    def test_effective_threshold_local_global(self) -> None:
        assert effective_min_similarity(scheme_id=None) == 0.55

    def test_build_context_empty(self) -> None:
        ctx = build_context([])
        assert "[CONTEXT]" in ctx
        assert "[/CONTEXT]" in ctx


class TestRetrieverGolden:
    def test_sc08_mid_cap_expense_filtered(self, vector_store_ready) -> None:
        result = retrieve(
            "What is the expense ratio for HDFC Mid Cap Fund?",
            persist_directory=VECTOR_STORE,
        )
        assert result.found
        assert result.scheme_id == "hdfc-mid-cap"
        assert result.chunks[0].section == "costs"
        assert result.chunks[0].scheme_id == "hdfc-mid-cap"
        assert result.citation_url
        assert "expense ratio" in document_to_content(result.chunks[0]).lower()
        assert "[CONTEXT]" in result.context

    def test_gold_exit_load(self, vector_store_ready) -> None:
        result = retrieve(
            "What is the exit load on HDFC Gold ETF Fund of Fund?",
            persist_directory=VECTOR_STORE,
        )
        assert result.found
        assert result.chunks[0].scheme_id == "hdfc-gold-etf-fof"
        assert result.chunks[0].section == "exit_load"

    def test_rt03_nifty_manager(self, vector_store_ready) -> None:
        result = retrieve(
            "Who manages the HDFC NIFTY 50 Index Fund?",
            persist_directory=VECTOR_STORE,
        )
        assert result.found
        assert result.chunks[0].scheme_id == "hdfc-nifty-50-index"
        assert result.chunks[0].section == "fund_management"

    def test_silver_min_sip(self, vector_store_ready) -> None:
        result = retrieve(
            "What is the minimum SIP for silver fund?",
            persist_directory=VECTOR_STORE,
        )
        assert result.found
        assert result.scheme_id == "hdfc-silver-etf-fof"
        assert result.chunks[0].section == "minimum_investment"

    def test_sc12_groww_url_in_query(self, vector_store_ready) -> None:
        url = "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth"
        result = retrieve(
            f"What is the risk level? {url}",
            persist_directory=VECTOR_STORE,
        )
        assert result.found
        assert result.scheme_id == "hdfc-equity"
        assert result.chunks[0].section == "risk"

    def test_rt10_tax_and_exit_load_top_k(self, vector_store_ready) -> None:
        result = retrieve(
            "tax and exit load for HDFC Equity Fund",
            persist_directory=VECTOR_STORE,
            top_k=5,
        )
        assert result.found
        sections = {h.section for h in result.chunks}
        assert "tax" in sections
        assert "exit_load" in sections

    def test_sc07_all_five_min_sip(self, vector_store_ready) -> None:
        result = retrieve(
            "What is the minimum SIP for all five schemes?",
            persist_directory=VECTOR_STORE,
        )
        assert result.found
        scheme_ids = {h.scheme_id for h in result.chunks}
        expected = {s.scheme_id for s in get_all_schemes()}
        assert scheme_ids == expected
        assert all(h.section == "minimum_investment" for h in result.chunks)

    def test_rt01_below_threshold_not_found(self, vector_store_ready) -> None:
        result = retrieve(
            "quantum physics mutual fund dividend policy",
            persist_directory=VECTOR_STORE,
            min_similarity=0.99,
        )
        assert not result.found
        assert result.message == NOT_FOUND_MESSAGE
        assert result.chunks == ()
        assert result.citation_url is None

    def test_generic_expense_without_scheme(self, vector_store_ready) -> None:
        result = retrieve("expense ratio", persist_directory=VECTOR_STORE)
        assert result.found
        assert result.scheme_id is None
        assert all(h.section == "costs" for h in result.chunks)

    def test_missing_index_raises(self) -> None:
        with pytest.raises(FileNotFoundError, match="Vector index not found"):
            retrieve("expense ratio", persist_directory="/nonexistent/chroma/path")
