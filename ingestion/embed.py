"""
Embedding providers for Phase 2 indexing and retrieval.

Supports:
- **local** — free Hugging Face models via ``sentence-transformers`` (BGE small/large)
- **openai** — paid ``text-embedding-3-*`` API (optional)
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import (
    BGE_LARGE_MODEL,
    BGE_SMALL_MODEL,
    EMBEDDING_PROVIDER_LOCAL,
    EMBEDDING_PROVIDER_OPENAI,
    get_settings,
)
from ingestion.chunk import ChunkValidationError

if TYPE_CHECKING:
    from ingestion.chunk import Chunk

logger = logging.getLogger(__name__)

# BGE v1.5 query prefix (asymmetric retrieval — use on queries only)
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# Heuristic thresholds for auto model pick (local provider only)
_BGE_LARGE_MIN_CHUNKS = 500
_BGE_LARGE_MAX_TEXT_CHARS = 4000


class EmbeddingError(ChunkValidationError):
    """Raised when embedding cannot be produced."""


def recommend_bge_model(chunks: list[Chunk] | None = None) -> str:
    """
    Choose BGE small vs large from chunk corpus shape.

    Current HDFC corpus (~45 chunks, max ~2.3k chars) → **small**.
    Large is for much bigger indexes or very long passages.
    """
    if chunks is None:
        from ingestion.chunk_store import load_all_chunks

        chunks = load_all_chunks()

    if not chunks:
        return BGE_SMALL_MODEL

    max_len = max(len(c.text) for c in chunks)
    if len(chunks) > _BGE_LARGE_MIN_CHUNKS or max_len > _BGE_LARGE_MAX_TEXT_CHARS:
        return BGE_LARGE_MODEL
    return BGE_SMALL_MODEL


def _normalize_model_alias(name: str) -> str:
    aliases = {
        "bge-small": BGE_SMALL_MODEL,
        "bge-large": BGE_LARGE_MODEL,
    }
    return aliases.get(name.strip().lower(), name)


def resolve_embedding_model(
    *,
    provider: str | None = None,
    model: str | None = None,
    chunks: list[Chunk] | None = None,
) -> str:
    """Resolve model name from settings, explicit override, or BGE auto-pick."""
    settings = get_settings()
    prov = (provider or settings.embedding_provider).lower().strip()

    if model:
        return _normalize_model_alias(model)

    configured = _normalize_model_alias(settings.embedding_model) if settings.embedding_model else ""

    if prov == EMBEDDING_PROVIDER_LOCAL:
        if configured in (BGE_SMALL_MODEL, BGE_LARGE_MODEL):
            return configured
        if settings.embedding_auto_bge or configured in ("bge-small", "bge-large"):
            return recommend_bge_model(chunks)
        return BGE_SMALL_MODEL

    return configured or "text-embedding-3-small"


@lru_cache(maxsize=2)
def _get_sentence_transformer(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise EmbeddingError(
            "sentence-transformers is required for local embeddings. "
            "Install: pip install sentence-transformers"
        ) from exc

    logger.info("Loading local embedding model: %s", model_name)
    return SentenceTransformer(model_name)


def _embed_openai(
    texts: list[str],
    *,
    api_key: str | None,
    model: str,
) -> list[list[float]]:
    settings = get_settings()
    key = api_key or settings.openai_api_key
    if not key:
        raise EmbeddingError(
            "OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai"
        )

    from openai import OpenAI

    client = OpenAI(api_key=key)
    response = client.embeddings.create(input=texts, model=model)
    return [item.embedding for item in sorted(response.data, key=lambda d: d.index)]


def _embed_local(texts: list[str], *, model: str, is_query: bool) -> list[list[float]]:
    encoder = _get_sentence_transformer(model)
    inputs = texts
    if is_query:
        inputs = [
            t if t.startswith(BGE_QUERY_PREFIX) else f"{BGE_QUERY_PREFIX}{t}"
            for t in texts
        ]
    vectors = encoder.encode(
        inputs,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vectors.tolist()


def embed_texts(
    texts: list[str],
    *,
    api_key: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    chunks: list[Chunk] | None = None,
) -> list[list[float]]:
    """
    Embed document / chunk strings for indexing (passages).

    Uses ``EMBEDDING_PROVIDER`` from settings: ``local`` (default) or ``openai``.
    """
    if not texts:
        return []

    settings = get_settings()
    prov = (provider or settings.embedding_provider).lower().strip()
    resolved = resolve_embedding_model(provider=prov, model=model, chunks=chunks)

    if prov == EMBEDDING_PROVIDER_OPENAI:
        return _embed_openai(texts, api_key=api_key, model=resolved)

    if prov == EMBEDDING_PROVIDER_LOCAL:
        return _embed_local(texts, model=resolved, is_query=False)

    raise EmbeddingError(
        f"Unknown EMBEDDING_PROVIDER={prov!r}; use {EMBEDDING_PROVIDER_LOCAL!r} or "
        f"{EMBEDDING_PROVIDER_OPENAI!r}"
    )


def embed_query(
    texts: list[str],
    *,
    model: str | None = None,
    provider: str | None = None,
) -> list[list[float]]:
    """Embed user queries (BGE query prefix applied when provider is local)."""
    if not texts:
        return []

    settings = get_settings()
    prov = (provider or settings.embedding_provider).lower().strip()
    resolved = resolve_embedding_model(provider=prov, model=model)

    if prov == EMBEDDING_PROVIDER_OPENAI:
        return _embed_openai(texts, api_key=None, model=resolved)

    if prov == EMBEDDING_PROVIDER_LOCAL:
        return _embed_local(texts, model=resolved, is_query=True)

    raise EmbeddingError(f"Unknown EMBEDDING_PROVIDER={prov!r}")
