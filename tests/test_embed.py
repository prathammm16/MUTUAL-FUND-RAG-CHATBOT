"""Embedding provider tests (local BGE + OpenAI routing)."""

from unittest.mock import MagicMock, patch

import pytest

from app.config import BGE_LARGE_MODEL, BGE_SMALL_MODEL
from ingestion.chunk import chunk_scheme
from ingestion.embed import (
    BGE_QUERY_PREFIX,
    embed_query,
    embed_texts,
    recommend_bge_model,
    resolve_embedding_model,
)
from ingestion.parse import parse_document

SAMPLE = __import__("pathlib").Path(__file__).parent / "fixtures" / "sample_mid_cap.md"


@pytest.fixture
def mid_cap_chunks():
    raw = SAMPLE.read_text(encoding="utf-8")
    parsed = parse_document(raw, scheme_id="hdfc-mid-cap")
    return chunk_scheme(parsed)


class TestRecommendBge:
    def test_recommend_small_for_fixture(self, mid_cap_chunks) -> None:
        assert recommend_bge_model(mid_cap_chunks) == BGE_SMALL_MODEL

    def test_recommend_large_for_huge_corpus(self) -> None:
        from ingestion.chunk import Chunk

        big = Chunk(
            chunk_id="x:objective:0",
            scheme_id="hdfc-equity",
            scheme_name="HDFC Equity Fund Direct Growth",
            source_url="https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth",
            section="objective",
            content="x",
            text="x" * 5000,
        )
        assert recommend_bge_model([big]) == BGE_LARGE_MODEL


class TestResolveModel:
    def test_local_default_is_bge_small(self, monkeypatch) -> None:
        monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
        monkeypatch.setenv("EMBEDDING_MODEL", "")
        from app.config import get_settings

        get_settings.cache_clear()
        assert resolve_embedding_model(provider="local") == BGE_SMALL_MODEL
        get_settings.cache_clear()

    def test_explicit_large_override(self) -> None:
        assert (
            resolve_embedding_model(
                provider="local",
                model=BGE_LARGE_MODEL,
            )
            == BGE_LARGE_MODEL
        )


class TestLocalEmbed:
    @pytest.fixture(autouse=True)
    def _sentence_transformers_backend(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_BACKEND", "sentence_transformers")
        from app.config import get_settings

        get_settings.cache_clear()
        yield
        get_settings.cache_clear()

    @patch("ingestion.embed._get_sentence_transformer")
    def test_embed_texts_passages(self, mock_get_model, mid_cap_chunks) -> None:
        mock_model = MagicMock()
        encoded = MagicMock()
        encoded.tolist.return_value = [[0.1, 0.2], [0.3, 0.4]]
        mock_model.encode.return_value = encoded
        mock_get_model.return_value = mock_model

        out = embed_texts(
            ["passage one", "passage two"],
            provider="local",
            model=BGE_SMALL_MODEL,
        )
        assert len(out) == 2
        mock_model.encode.assert_called_once()
        call_kw = mock_model.encode.call_args.kwargs
        assert call_kw["normalize_embeddings"] is True
        assert not mock_model.encode.call_args.args[0][0].startswith(BGE_QUERY_PREFIX)

    @patch("ingestion.embed._get_sentence_transformer")
    def test_embed_query_adds_prefix(self, mock_get_model) -> None:
        mock_model = MagicMock()
        encoded = MagicMock()
        encoded.tolist.return_value = [[1.0, 0.0]]
        mock_model.encode.return_value = encoded
        mock_get_model.return_value = mock_model

        embed_query(["expense ratio mid cap"], provider="local", model=BGE_SMALL_MODEL)
        encoded = mock_model.encode.call_args.args[0]
        assert encoded[0].startswith(BGE_QUERY_PREFIX)


class TestOpenAIEmbed:
    def test_openai_requires_key(self, monkeypatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "")
        from app.config import get_settings

        get_settings.cache_clear()
        with pytest.raises(Exception, match="OPENAI_API_KEY"):
            embed_texts(["hello"], provider="openai")
        get_settings.cache_clear()
