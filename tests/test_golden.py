"""Phase 5 — RAG backend, validator, and API golden cases."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_scheme, get_settings, is_allowlisted_source_url
from app.main import create_app
from app.rag.backend import ResponseType, run_rag
from app.rag.validator import count_sentences, validate_and_fix
from ingestion.index import collection_exists

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VECTOR_STORE = str(PROJECT_ROOT / "vector_store")


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture(scope="module")
def vector_store_ready():
    pytest.importorskip("chromadb")
    if not collection_exists(VECTOR_STORE):
        pytest.skip("vector_store missing; run scripts/build_index.py --reset")


class TestValidator:
    def test_gn01_caps_at_three_sentences(self) -> None:
        url = "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
        bad = "One. Two. Three. Four. " + f"[link]({url})."
        result = validate_and_fix(
            bad,
            citation_url=url,
            footer="Last updated from sources: 2026-06-04",
        )
        assert count_sentences(result.answer) <= 3

    def test_gn05_appends_footer(self) -> None:
        url = "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
        result = validate_and_fix(
            f"Expense ratio is 0.70%. [page]({url}).",
            citation_url=url,
            footer="",
        )
        assert result.footer.startswith("Last updated from sources:")

    def test_gn06_advisory_leakage(self) -> None:
        url = "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth"
        with pytest.raises(Exception):
            validate_and_fix(
                "You should buy this fund. [page]({url}).",
                citation_url=url,
                footer="Last updated from sources: 2026-06-04",
            )

    def test_gn02_injects_citation(self) -> None:
        url = "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
        result = validate_and_fix(
            "The expense ratio is 0.73%.",
            citation_url=url,
            footer="Last updated from sources: 2026-06-04",
        )
        assert url in result.answer
        assert is_allowlisted_source_url(result.citation_url)

    def test_gn04_strips_non_allowlisted_url(self) -> None:
        url = "https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth"
        result = validate_and_fix(
            "Exit load is 1%. See https://en.wikipedia.org/wiki/Mutual_fund. "
            f"[scheme page]({url}).",
            citation_url=url,
            footer="Last updated from sources: 2026-06-04",
        )
        assert "wikipedia" not in result.answer.lower()
        assert is_allowlisted_source_url(result.citation_url)


class TestRagBackend:
    def test_refusal_advisory(self, vector_store_ready) -> None:
        result = run_rag(
            "Which fund is better, gold or silver?",
            force_template=True,
            persist_directory=VECTOR_STORE,
        )
        assert result.type == ResponseType.REFUSAL
        assert result.citation_url
        settings = get_settings()
        assert result.citation_url in (
            settings.amfi_education_url,
            settings.sebi_investor_url,
        )

    def test_refusal_performance(self, vector_store_ready) -> None:
        result = run_rag(
            "Compare 3Y returns of gold and silver",
            force_template=True,
            persist_directory=VECTOR_STORE,
        )
        assert result.type == ResponseType.REFUSAL

    def test_mid_cap_expense_answer(self, vector_store_ready) -> None:
        result = run_rag(
            "What is the expense ratio for HDFC Mid Cap Fund?",
            force_template=True,
            persist_directory=VECTOR_STORE,
        )
        assert result.type == ResponseType.ANSWER
        assert is_allowlisted_source_url(result.citation_url)
        assert "0.73" in result.answer or "expense" in result.answer.lower()
        assert result.footer.startswith("Last updated from sources:")
        assert count_sentences(result.answer) <= 3

    def test_nifty_manager_biographical(self, vector_store_ready) -> None:
        result = run_rag(
            "Who manages the HDFC NIFTY 50 Index Fund?",
            force_template=True,
            persist_directory=VECTOR_STORE,
        )
        assert result.type == ResponseType.ANSWER
        assert "hdfc-nifty-50-index" in result.citation_url or is_allowlisted_source_url(
            result.citation_url
        )
        assert count_sentences(result.answer) <= 3

    def test_not_found_high_threshold(self, vector_store_ready) -> None:
        from app.rag import retriever as retriever_mod

        original = retriever_mod.effective_min_similarity

        def _always_high(**_kwargs):
            return 0.99

        retriever_mod.effective_min_similarity = _always_high
        try:
            result = run_rag(
                "expense ratio HDFC Mid Cap",
                force_template=True,
                persist_directory=VECTOR_STORE,
            )
            assert result.type == ResponseType.NOT_FOUND
        finally:
            retriever_mod.effective_min_similarity = original


class TestApi:
    def test_ap07_schemes(self, client) -> None:
        resp = client.get("/api/schemes")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["schemes"]) == 5

    def test_health(self, client, vector_store_ready) -> None:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["index_chunk_count"] >= 40
        assert "corpus_version" in body

    def test_ap03_missing_message_422(self, client) -> None:
        resp = client.post("/api/chat", json={})
        assert resp.status_code == 422

    def test_in02_whitespace_400(self, client) -> None:
        resp = client.post("/api/chat", json={"message": "   "})
        assert resp.status_code == 400

    def test_in03_message_too_long_422(self, client) -> None:
        resp = client.post("/api/chat", json={"message": "x" * 4097})
        assert resp.status_code == 422

    def test_refusal_via_api(self, client, vector_store_ready) -> None:
        resp = client.post(
            "/api/chat",
            json={"message": "Which fund is better?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "refusal"
        assert data["answer"]

    def test_refusal_performance_via_api(self, client, vector_store_ready) -> None:
        resp = client.post(
            "/api/chat",
            json={"message": "Compare 3Y returns"},
        )
        assert resp.status_code == 200
        assert resp.json()["type"] == "refusal"

    def test_factual_via_api(self, client, vector_store_ready) -> None:
        resp = client.post(
            "/api/chat",
            json={"message": "What is the exit load on HDFC Gold ETF Fund of Fund?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "answer"
        assert is_allowlisted_source_url(data["citation_url"])
        assert data["footer"].startswith("Last updated from sources:")
        assert count_sentences(data["answer"]) <= 3

    def test_silver_sip_via_api(self, client, vector_store_ready) -> None:
        resp = client.post(
            "/api/chat",
            json={"message": "Min SIP for silver fund?"},
        )
        assert resp.status_code == 200
        assert resp.json()["type"] == "answer"


# RT-09 — one factual golden per scheme; citation must match queried scheme (not cross-scheme)
SCHEME_API_GOLDEN = [
    (
        "hdfc-silver-etf-fof",
        "What is the expense ratio of HDFC Silver ETF FoF?",
        ["0.21"],
    ),
    (
        "hdfc-mid-cap",
        "What is the expense ratio for HDFC Mid Cap Fund?",
        ["0.73"],
    ),
    (
        "hdfc-equity",
        "What is the expense ratio of HDFC Equity Fund?",
        ["0.68"],
    ),
    (
        "hdfc-gold-etf-fof",
        "What is the exit load on HDFC Gold ETF Fund of Fund?",
        ["1%"],
    ),
    (
        "hdfc-nifty-50-index",
        "Who manages the HDFC NIFTY 50 Index Fund?",
        [],
    ),
]


class TestPerSchemeGolden:
    """RT-09 — per-scheme factual answers with correct citation URL."""

    @pytest.mark.parametrize(
        "scheme_id,message,snippets",
        SCHEME_API_GOLDEN,
        ids=[row[0] for row in SCHEME_API_GOLDEN],
    )
    def test_rt09_factual_per_scheme(
        self,
        vector_store_ready,
        scheme_id: str,
        message: str,
        snippets: list[str],
    ) -> None:
        result = run_rag(
            message,
            force_template=True,
            persist_directory=VECTOR_STORE,
        )
        scheme = get_scheme(scheme_id)
        assert scheme is not None
        assert result.type == ResponseType.ANSWER
        assert result.citation_url == scheme.source_url
        answer_lower = result.answer.lower()
        for snippet in snippets:
            assert snippet.lower() in answer_lower
        assert count_sentences(result.answer) <= 3

    @pytest.mark.parametrize(
        "scheme_id,message,snippets",
        SCHEME_API_GOLDEN,
        ids=[row[0] for row in SCHEME_API_GOLDEN],
    )
    def test_rt09_factual_per_scheme_via_api(
        self,
        client,
        vector_store_ready,
        scheme_id: str,
        message: str,
        snippets: list[str],
    ) -> None:
        scheme = get_scheme(scheme_id)
        assert scheme is not None
        resp = client.post("/api/chat", json={"message": message})
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "answer"
        assert data["citation_url"] == scheme.source_url
        for snippet in snippets:
            assert snippet.lower() in data["answer"].lower()


class TestComplianceApi:
    def test_pii_refusal_via_api(self, client) -> None:
        resp = client.post(
            "/api/chat",
            json={"message": "My PAN is ABCDE1234F, which fund should I buy?"},
        )
        assert resp.status_code == 200
        assert resp.json()["type"] == "refusal"

    def test_out_of_corpus_via_api(self, client) -> None:
        resp = client.post(
            "/api/chat",
            json={"message": "What is the expense ratio of SBI Flexi Cap?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "refusal"
        assert "HDFC" in data["answer"] or "five" in data["answer"].lower()
