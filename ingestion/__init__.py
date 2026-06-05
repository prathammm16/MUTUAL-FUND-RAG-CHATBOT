"""Offline ingestion pipeline (parse, chunk, index) — Phase 1+."""

from ingestion.chunk import (
    Chunk,
    ChunkValidationError,
    chunk_corpus,
    chunk_scheme,
    dedupe_chunks,
    format_prefix,
    validate_chunk,
    validate_chunks,
)
from ingestion.chunk_store import (
    DEFAULT_CHUNKS_DIR,
    build_chunks_from_corpus_dir,
    load_all_chunks,
    write_all_chunks,
)
from ingestion.corpus import (
    CorpusArtifacts,
    build_corpus_from_imports,
    load_corpus,
    write_corpus_file,
)
from ingestion.fetch import RawArtifacts, fetch_all_schemes, fetch_scheme_to_raw
from ingestion.embed import embed_query, embed_texts, recommend_bge_model
from ingestion.index import (
    COLLECTION_NAME,
    DEFAULT_INDEX_DIR,
    RetrievedChunk,
    chunk_to_metadata,
    collection_exists,
    index_corpus,
    query_chunks,
    validate_indexed_store,
)
from ingestion.load import load_all_raw, parse_all_imports
from ingestion.parse import ParsedScheme, parse_document, strip_noise
from ingestion.validate import validate_corpus, validate_corpus_dir

__all__ = [
    "COLLECTION_NAME",
    "Chunk",
    "ChunkValidationError",
    "CorpusArtifacts",
    "DEFAULT_CHUNKS_DIR",
    "DEFAULT_INDEX_DIR",
    "ParsedScheme",
    "RawArtifacts",
    "build_chunks_from_corpus_dir",
    "build_corpus_from_imports",
    "chunk_corpus",
    "chunk_scheme",
    "chunk_to_metadata",
    "dedupe_chunks",
    "embed_query",
    "embed_texts",
    "fetch_all_schemes",
    "fetch_scheme_to_raw",
    "format_prefix",
    "RetrievedChunk",
    "collection_exists",
    "index_corpus",
    "query_chunks",
    "validate_indexed_store",
    "load_all_chunks",
    "load_all_raw",
    "load_corpus",
    "parse_all_imports",
    "recommend_bge_model",
    "parse_document",
    "strip_noise",
    "validate_chunk",
    "validate_chunks",
    "validate_corpus",
    "validate_corpus_dir",
    "write_all_chunks",
    "write_corpus_file",
]
