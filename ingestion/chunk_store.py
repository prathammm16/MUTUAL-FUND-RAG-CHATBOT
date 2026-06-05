"""
Persist and load Phase 1 chunks under ``data/chunks/``.

Outputs per scheme: ``{scheme_id}.json``, ``{scheme_id}.md``, plus ``all_chunks.json``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ingestion.chunk import (
    Chunk,
    chunk_corpus,
    dedupe_chunks,
    validate_chunks,
)
from ingestion.corpus import DEFAULT_CORPUS_DIR, load_corpus
from ingestion.parse import ParsedScheme

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHUNKS_DIR = _PROJECT_ROOT / "data" / "chunks"

_CHUNK_VERSION = 1
EXPECTED_CHUNKS_PER_SCHEME = 9
MIN_TOTAL_CHUNKS = 40


class ChunkStoreError(ValueError):
    """Raised when chunk build or validation fails (Phase 1 gate)."""


def chunk_to_dict(chunk: Chunk) -> dict[str, Any]:
    return {
        "chunk_id": chunk.chunk_id,
        "scheme_id": chunk.scheme_id,
        "scheme_name": chunk.scheme_name,
        "source_url": chunk.source_url,
        "section": chunk.section,
        "content": chunk.content,
        "text": chunk.text,
        "last_updated": chunk.last_updated,
    }


def chunk_from_dict(data: dict[str, Any]) -> Chunk:
    return Chunk(
        chunk_id=data["chunk_id"],
        scheme_id=data["scheme_id"],
        scheme_name=data["scheme_name"],
        source_url=data["source_url"],
        section=data["section"],
        content=data["content"],
        text=data["text"],
        last_updated=data.get("last_updated"),
    )


def chunks_paths(scheme_id: str, chunks_dir: Path | None = None) -> tuple[Path, Path]:
    base = chunks_dir or DEFAULT_CHUNKS_DIR
    return base / f"{scheme_id}.json", base / f"{scheme_id}.md"


def chunk_to_markdown_scheme(chunks: list[Chunk], scheme_name: str, source_url: str) -> str:
    lines = [f"Source URL: {source_url}", "", f"# Chunks — {scheme_name}", ""]
    for c in chunks:
        lines.extend(
            [
                f"## {c.chunk_id}",
                f"Section: {c.section}",
                "",
                c.content,
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def build_chunks_from_corpus(
    corpus: dict[str, ParsedScheme],
    *,
    dedupe: bool = True,
) -> list[Chunk]:
    """Chunk parsed corpus with dedupe and validation (Phase 1.6)."""
    chunks = chunk_corpus(corpus)
    if not chunks:
        raise ChunkStoreError("no chunks produced from corpus")
    if dedupe:
        chunks = dedupe_chunks(chunks)
    validate_chunks(chunks)
    return chunks


def write_scheme_chunks(
    chunks: list[Chunk],
    scheme_id: str,
    chunks_dir: Path | None = None,
) -> tuple[Path, Path]:
    """Write ``data/chunks/{scheme_id}.json`` and ``.md``."""
    scheme_chunks = [c for c in chunks if c.scheme_id == scheme_id]
    if not scheme_chunks:
        raise ChunkStoreError(f"no chunks for scheme {scheme_id}")

    base = chunks_dir or DEFAULT_CHUNKS_DIR
    base.mkdir(parents=True, exist_ok=True)
    json_path, md_path = chunks_paths(scheme_id, base)

    payload = {
        "chunk_version": _CHUNK_VERSION,
        "scheme_id": scheme_id,
        "scheme_name": scheme_chunks[0].scheme_name,
        "source_url": scheme_chunks[0].source_url,
        "chunk_count": len(scheme_chunks),
        "chunks": [chunk_to_dict(c) for c in scheme_chunks],
    }
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(
        chunk_to_markdown_scheme(
            scheme_chunks,
            scheme_chunks[0].scheme_name,
            scheme_chunks[0].source_url,
        ),
        encoding="utf-8",
    )
    return json_path, md_path


def write_all_chunks(
    chunks: list[Chunk],
    chunks_dir: Path | None = None,
) -> Path:
    """Write per-scheme chunk files and ``all_chunks.json``."""
    base = chunks_dir or DEFAULT_CHUNKS_DIR
    base.mkdir(parents=True, exist_ok=True)

    scheme_ids = sorted({c.scheme_id for c in chunks})
    for scheme_id in scheme_ids:
        write_scheme_chunks(chunks, scheme_id, base)
        logger.info("Wrote chunks for %s", scheme_id)

    all_path = base / "all_chunks.json"
    all_path.write_text(
        json.dumps(
            {
                "chunk_version": _CHUNK_VERSION,
                "chunk_count": len(chunks),
                "chunks": [chunk_to_dict(c) for c in chunks],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    logger.info("Wrote %s (%d chunks)", all_path, len(chunks))
    return all_path


def load_scheme_chunks(
    scheme_id: str,
    chunks_dir: Path | None = None,
) -> list[Chunk]:
    json_path, _ = chunks_paths(scheme_id, chunks_dir)
    if not json_path.is_file():
        return []
    data = json.loads(json_path.read_text(encoding="utf-8"))
    return [chunk_from_dict(c) for c in data.get("chunks") or []]


def load_all_chunks(chunks_dir: Path | None = None) -> list[Chunk]:
    """Load chunks from per-scheme JSON files (falls back to ``all_chunks.json``)."""
    base = chunks_dir or DEFAULT_CHUNKS_DIR
    scheme_files = sorted(
        p for p in base.glob("*.json") if p.name != "all_chunks.json"
    )
    if scheme_files:
        chunks: list[Chunk] = []
        for json_path in scheme_files:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            chunks.extend(chunk_from_dict(c) for c in data.get("chunks") or [])
        if chunks:
            return chunks

    all_path = base / "all_chunks.json"
    if all_path.is_file():
        data = json.loads(all_path.read_text(encoding="utf-8"))
        return [chunk_from_dict(c) for c in data.get("chunks") or []]

    return []


def build_chunks_from_corpus_dir(
    corpus_dir: Path | None = None,
    chunks_dir: Path | None = None,
    *,
    dedupe: bool = True,
) -> list[Chunk]:
    """Load corpus, chunk, write ``data/chunks/``, return chunk list."""
    corpus = load_corpus(corpus_dir or DEFAULT_CORPUS_DIR)
    if not corpus:
        raise ChunkStoreError("no corpus found; run build_corpus.py first")
    chunks = build_chunks_from_corpus(corpus, dedupe=dedupe)
    write_all_chunks(chunks, chunks_dir)
    return chunks


def validate_chunks_store(
    chunks_dir: Path | None = None,
    *,
    require_all_schemes: bool = True,
) -> list[str]:
    """
    Phase 1 chunk gate checks. Returns error messages (empty if OK).
    """
    from app.config import get_all_schemes

    base = chunks_dir or DEFAULT_CHUNKS_DIR
    errors: list[str] = []
    chunks = load_all_chunks(base)

    if not chunks:
        return ["no chunks in data/chunks; run build_chunks.py"]

    if len(chunks) < MIN_TOTAL_CHUNKS:
        errors.append(f"expected >={MIN_TOTAL_CHUNKS} chunks, got {len(chunks)}")

    by_scheme: dict[str, list[Chunk]] = {}
    for c in chunks:
        by_scheme.setdefault(c.scheme_id, []).append(c)

    expected_ids = {s.scheme_id for s in get_all_schemes()}
    if require_all_schemes:
        missing = sorted(expected_ids - set(by_scheme))
        if missing:
            errors.append(f"missing chunk files for schemes: {', '.join(missing)}")

    for scheme_id, scheme_chunks in by_scheme.items():
        if len(scheme_chunks) < 8:
            errors.append(f"{scheme_id}: only {len(scheme_chunks)} chunks")
        if not any(c.section == "fund_management" for c in scheme_chunks):
            errors.append(f"{scheme_id}: no fund_management chunk")
        if not any(c.section == "costs" for c in scheme_chunks):
            errors.append(f"{scheme_id}: no costs chunk")
        try:
            validate_chunks(scheme_chunks)
        except Exception as exc:
            errors.append(f"{scheme_id}: {exc}")

    return errors
