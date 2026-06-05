"""
Embed chunks and upsert to Chroma (Phase 2).

Loads pre-built chunks from ``data/chunks/`` (Phase 1.7).
Collection: ``hdfc_groww_corpus``
"""

from __future__ import annotations

import gc
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.config import get_all_schemes, get_settings, is_allowlisted_source_url
from ingestion.chunk_store import MIN_TOTAL_CHUNKS
from ingestion.chunk import Chunk, ChunkValidationError, validate_chunks
from ingestion.embed import embed_texts as _embed_texts
from ingestion.embed import resolve_embedding_model
from ingestion.chunk_store import (
    DEFAULT_CHUNKS_DIR,
    build_chunks_from_corpus_dir,
    load_all_chunks,
)
from ingestion.corpus import DEFAULT_CORPUS_DIR

if TYPE_CHECKING:
    import chromadb
    from chromadb.api.models.Collection import Collection

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX_DIR = _PROJECT_ROOT / "data" / "index"

COLLECTION_NAME = "hdfc_groww_corpus"

# Back-compat alias for tests / callers
ChunkIndexError = ChunkValidationError


def chunk_to_metadata(chunk: Chunk, *, ingested_at: str | None = None) -> dict[str, str]:
    """Build Chroma-safe metadata dict for one chunk."""
    return {
        "chunk_id": chunk.chunk_id,
        "scheme_id": chunk.scheme_id,
        "scheme_name": chunk.scheme_name,
        "source_url": chunk.source_url,
        "section": chunk.section,
        "last_updated": chunk.last_updated or "",
        "ingested_at": ingested_at or "",
    }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def embed_texts(texts: list[str], *, api_key: str | None = None, model: str | None = None) -> list[list[float]]:
    """Embed chunk passages (delegates to ``ingestion.embed``)."""
    return _embed_texts(texts, api_key=api_key, model=model)


def resolve_index_dir(persist_directory: str | Path | None = None) -> Path:
    """Return absolute path to Chroma persistence directory."""
    if persist_directory is not None:
        return Path(persist_directory).resolve()
    configured = get_settings().vector_store_path
    if configured:
        p = Path(configured)
        return p.resolve() if p.is_absolute() else (_PROJECT_ROOT / p).resolve()
    return DEFAULT_INDEX_DIR


def get_chroma_client(persist_directory: str | None = None) -> chromadb.PersistentClient:
    import chromadb

    path = resolve_index_dir(persist_directory)
    path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(path))


def get_or_create_collection(
    client: chromadb.PersistentClient,
    name: str = COLLECTION_NAME,
) -> Collection:
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_chunks(
    collection: Collection,
    chunks: list[Chunk],
    embeddings: list[list[float]],
    *,
    ingested_at: str | None = None,
) -> int:
    """Upsert chunks into a Chroma collection."""
    if len(chunks) != len(embeddings):
        raise ChunkIndexError(
            f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) length mismatch"
        )
    if not chunks:
        return 0

    ingested = ingested_at or _utc_now_iso()
    validate_chunks(chunks)

    collection.upsert(
        ids=[c.chunk_id for c in chunks],
        documents=[c.text for c in chunks],
        embeddings=embeddings,
        metadatas=[chunk_to_metadata(c, ingested_at=ingested) for c in chunks],
    )
    return len(chunks)


def load_chunks_for_index(chunks_dir=None) -> list[Chunk]:
    """Load Phase 1 chunk store; build from corpus if missing."""
    base = chunks_dir or DEFAULT_CHUNKS_DIR
    chunks = load_all_chunks(base)
    if chunks:
        validate_chunks(chunks)
        return chunks

    logger.warning("data/chunks empty; building from corpus")
    return build_chunks_from_corpus_dir(corpus_dir=DEFAULT_CORPUS_DIR, chunks_dir=base)


def index_corpus(
    corpus_dir=None,
    *,
    chunks_dir: Path | None = None,
    persist_directory: str | None = None,
    reset_collection: bool = False,
    batch_size: int = 64,
    ingested_at: str | None = None,
) -> int:
    """
    Load Phase 1 chunks, embed, and upsert to Chroma.

    Returns total chunks indexed.
    """
    chunks = load_chunks_for_index(chunks_dir)
    if not chunks:
        raise ChunkIndexError("no chunks available; complete Phase 1 build first")

    settings = get_settings()
    ingested = ingested_at or settings.ingested_at or _utc_now_iso()
    embed_model = resolve_embedding_model(chunks=chunks)
    logger.info(
        "Embedding %d chunks with provider=%s model=%s",
        len(chunks),
        settings.embedding_provider,
        embed_model,
    )

    client = get_chroma_client(persist_directory)
    if reset_collection:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

    collection = get_or_create_collection(client)
    total = 0

    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        embeddings = _embed_texts(
            [c.text for c in batch],
            model=embed_model,
            chunks=chunks,
        )
        total += upsert_chunks(collection, batch, embeddings, ingested_at=ingested)

    logger.info(
        "Indexed %d chunks into %s at %s",
        total,
        COLLECTION_NAME,
        persist_directory or get_settings().vector_store_path,
    )
    del client, collection
    gc.collect()
    return total


def get_collection(
    persist_directory: str | None = None,
    name: str = COLLECTION_NAME,
) -> Collection:
    """Return an existing Chroma collection (for retrieval smoke tests)."""
    client = get_chroma_client(persist_directory)
    return client.get_collection(name=name)


def close_chroma_clients() -> None:
    """Best-effort release of Chroma SQLite handles (Windows daily re-ingest)."""
    gc.collect()


def collection_exists(persist_directory: str | None = None, name: str = COLLECTION_NAME) -> bool:
    """True if the named collection is present on disk."""
    client = get_chroma_client(persist_directory)
    try:
        client.get_collection(name=name)
        return True
    except Exception:
        return False
    finally:
        del client
        gc.collect()


def get_indexed_chunk_count(persist_directory: str | None = None, name: str = COLLECTION_NAME) -> int:
    """Return number of vectors in the collection (0 if missing)."""
    if not collection_exists(persist_directory, name):
        return 0
    client = get_chroma_client(persist_directory)
    try:
        collection = client.get_collection(name=name)
        return collection.count()
    finally:
        del client, collection
        gc.collect()


def distance_to_similarity(distance: float) -> float:
    """Map Chroma cosine distance to similarity (1 = identical for normalized vectors)."""
    return 1.0 - distance


@dataclass(frozen=True)
class RetrievedChunk:
    """One chunk returned from vector search."""

    chunk_id: str
    scheme_id: str
    scheme_name: str
    source_url: str
    section: str
    document: str
    similarity: float
    last_updated: str
    ingested_at: str


def build_chroma_where(
    *,
    scheme_id: str | None = None,
    section: str | None = None,
) -> dict[str, Any] | None:
    """Build Chroma metadata filter (single field or ``$and``)."""
    clauses: list[dict[str, Any]] = []
    if scheme_id:
        clauses.append({"scheme_id": scheme_id})
    if section:
        clauses.append({"section": section})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def query_chunks(
    query_text: str,
    *,
    n_results: int | None = None,
    scheme_id: str | None = None,
    section: str | None = None,
    min_similarity: float | None = None,
    persist_directory: str | None = None,
) -> list[RetrievedChunk]:
    """
    Embed a query and search Chroma (uses ``embed_query`` for BGE prefix).

    Filters by ``scheme_id`` and/or ``section`` when provided.
    Drops results below ``min_similarity``.
    """
    from ingestion.embed import embed_query

    settings = get_settings()
    top_k = n_results or settings.top_k
    threshold = (
        min_similarity
        if min_similarity is not None
        else settings.similarity_threshold
    )

    collection = get_collection(persist_directory)
    query_embedding = embed_query([query_text])[0]

    where = build_chroma_where(scheme_id=scheme_id, section=section)

    raw = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,
        include=["metadatas", "documents", "distances"],
    )

    hits: list[RetrievedChunk] = []
    ids = raw.get("ids") or [[]]
    if not ids or not ids[0]:
        return hits

    for chunk_id, meta, doc, dist in zip(
        ids[0],
        raw["metadatas"][0],
        raw["documents"][0],
        raw["distances"][0],
    ):
        similarity = distance_to_similarity(dist)
        if similarity < threshold:
            continue
        hits.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                scheme_id=meta.get("scheme_id", ""),
                scheme_name=meta.get("scheme_name", ""),
                source_url=meta.get("source_url", ""),
                section=meta.get("section", ""),
                document=doc or "",
                similarity=similarity,
                last_updated=meta.get("last_updated", ""),
                ingested_at=meta.get("ingested_at", ""),
            )
        )
    return hits


def validate_indexed_store(
    persist_directory: str | None = None,
    *,
    require_all_schemes: bool = True,
) -> list[str]:
    """
    Phase 2 gate checks on Chroma collection. Returns error strings (empty if OK).
    """
    errors: list[str] = []
    path = persist_directory or get_settings().vector_store_path

    if not collection_exists(persist_directory):
        return [f"Chroma collection {COLLECTION_NAME!r} not found under {path}"]

    count = get_indexed_chunk_count(persist_directory)
    if count < MIN_TOTAL_CHUNKS:
        errors.append(f"expected >={MIN_TOTAL_CHUNKS} indexed chunks, got {count}")

    client = get_chroma_client(persist_directory)
    collection = client.get_collection(name=COLLECTION_NAME)
    all_rows = collection.get(include=["metadatas"])
    del client, collection
    gc.collect()
    metas = all_rows.get("metadatas") or []
    scheme_ids_found: set[str] = set()
    has_fund_management = False
    has_costs = False

    for meta in metas:
        if not meta:
            continue
        sid = meta.get("scheme_id", "")
        scheme_ids_found.add(sid)
        section = meta.get("section", "")
        if section == "fund_management":
            has_fund_management = True
        if section == "costs":
            has_costs = True
        url = meta.get("source_url", "")
        if not url or not is_allowlisted_source_url(url):
            errors.append(f"invalid source_url in index: {url!r}")
        if not meta.get("ingested_at"):
            errors.append(f"missing ingested_at on chunk {meta.get('chunk_id')}")

    if not has_fund_management:
        errors.append("no fund_management chunks in index sample")
    if not has_costs:
        errors.append("no costs chunks in index sample")

    if require_all_schemes:
        expected = {s.scheme_id for s in get_all_schemes()}
        missing = sorted(expected - scheme_ids_found)
        if missing and count < len(expected) * 8:
            errors.append(f"index may be missing schemes: {', '.join(missing)}")

    return errors
