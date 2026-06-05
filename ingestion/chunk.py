"""
Chunk parsed corpus for embedding (Phase 1 task 1.6).

Prefix template: ``Scheme: {scheme_name} | Section: {section} | {content}``
Fund-management blocks stay intact per manager.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass

from app.config import is_allowlisted_source_url
from ingestion.corpus import load_corpus
from ingestion.parse import ParsedScheme

logger = logging.getLogger(__name__)


class ChunkValidationError(ValueError):
    """Raised when a chunk fails validation (IG-10, Phase 1 gate)."""

PREFIX_TEMPLATE = "Scheme: {scheme_name} | Section: {section} | {content}"

# One chunk per section (exit load, tax, key metrics).
_SINGLE_CHUNK_SECTIONS: frozenset[str] = frozenset(
    {
        "costs",
        "exit_load",
        "tax",
        "minimum_investment",
        "risk",
        "benchmark",
    }
)

# Long narrative: ~500–800 tokens (~2400 chars), overlap ~50–100 tokens (~300 chars).
_MAX_NARRATIVE_CHARS = 2400
_NARRATIVE_OVERLAP_CHARS = 300

@dataclass(frozen=True)
class Chunk:
    """One embeddable unit with full metadata for store and index (Phase 1.6 / 2.2)."""

    chunk_id: str
    scheme_id: str
    scheme_name: str
    source_url: str
    section: str
    content: str
    text: str
    last_updated: str | None = None


def format_prefix(scheme_name: str, section: str, content: str) -> str:
    """Apply the architecture prefix template for embeddings."""
    return PREFIX_TEMPLATE.format(
        scheme_name=scheme_name,
        section=section,
        content=content.strip(),
    )


def make_chunk_id(scheme_id: str, section: str, index: int) -> str:
    return f"{scheme_id}:{section}:{index}"


_MANAGER_HEADING_RE = re.compile(
    r"(?:^|\n)(?:Fund\s+manager|Manager)\s*:",
    re.IGNORECASE | re.MULTILINE,
)


def _split_fund_management(content: str) -> list[str]:
    """
    Split fund management into per-manager blocks (FM-03, architecture §5.3).

    Keeps name, tenure, education, experience, and "also manages" together.
    Single-manager sections stay one chunk (including section heading line).
    """
    text = content.strip()
    if not text:
        return []

    manager_hits = list(_MANAGER_HEADING_RE.finditer(text))
    if len(manager_hits) <= 1:
        return [text]

    blocks: list[str] = []
    for i, match in enumerate(manager_hits):
        start = match.start()
        end = manager_hits[i + 1].start() if i + 1 < len(manager_hits) else len(text)
        block = text[start:end].strip()
        if block:
            blocks.append(block)
    return blocks if blocks else [text]


def _split_narrative(content: str) -> list[str]:
    """Split long objective/about text by paragraph with overlap."""
    text = content.strip()
    if not text:
        return []
    if len(text) <= _MAX_NARRATIVE_CHARS:
        return [text]

    paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
    if not paragraphs:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if current:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0

    for para in paragraphs:
        para_len = len(para) + (2 if current else 0)
        if current and current_len + para_len > _MAX_NARRATIVE_CHARS:
            flush()
            if chunks:
                tail = chunks[-1]
                overlap = tail[-_NARRATIVE_OVERLAP_CHARS:].strip()
                if overlap:
                    current = [overlap]
                    current_len = len(overlap)
        current.append(para)
        current_len += para_len

    flush()
    return chunks if chunks else [text]


def _section_pieces(section: str, content: str) -> list[str]:
    if not content.strip():
        return []
    if section == "fund_management":
        return _split_fund_management(content)
    if section == "objective":
        return _split_narrative(content)
    if section in _SINGLE_CHUNK_SECTIONS:
        return [content.strip()]
    return [content.strip()]


def chunk_scheme(parsed: ParsedScheme) -> list[Chunk]:
    """Build chunks for one parsed scheme."""
    last_updated = parsed.last_updated or ""
    chunks: list[Chunk] = []

    for section, content in sorted(parsed.sections.items()):
        for index, piece in enumerate(_section_pieces(section, content)):
            chunk_id = make_chunk_id(parsed.scheme_id, section, index)
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    scheme_id=parsed.scheme_id,
                    scheme_name=parsed.scheme_name,
                    source_url=parsed.source_url,
                    section=section,
                    content=piece,
                    text=format_prefix(parsed.scheme_name, section, piece),
                    last_updated=last_updated or None,
                )
            )

    return chunks


def chunk_corpus(corpus: dict[str, ParsedScheme]) -> list[Chunk]:
    """Chunk all schemes in a loaded corpus dict."""
    all_chunks: list[Chunk] = []
    for scheme_id in sorted(corpus.keys()):
        all_chunks.extend(chunk_scheme(corpus[scheme_id]))
    return all_chunks


def chunk_corpus_dir(corpus_dir=None) -> list[Chunk]:
    """Load corpus from disk and return chunks."""
    return chunk_corpus(load_corpus(corpus_dir))


def validate_chunk(chunk: Chunk) -> None:
    """Reject chunks missing allowlisted ``source_url`` or required fields (IG-10)."""
    if not chunk.chunk_id:
        raise ChunkValidationError("chunk_id is required")
    if not chunk.scheme_id:
        raise ChunkValidationError("scheme_id is required")
    if not chunk.scheme_name:
        raise ChunkValidationError("scheme_name is required")
    if not chunk.section:
        raise ChunkValidationError("section is required")
    if not chunk.text.strip():
        raise ChunkValidationError(f"empty text for chunk {chunk.chunk_id}")
    if not chunk.source_url:
        raise ChunkValidationError(f"missing source_url on chunk {chunk.chunk_id}")
    if not is_allowlisted_source_url(chunk.source_url):
        raise ChunkValidationError(
            f"source_url not allowlisted on chunk {chunk.chunk_id}: {chunk.source_url}"
        )


def validate_chunks(chunks: list[Chunk]) -> None:
    for chunk in chunks:
        validate_chunk(chunk)


def dedupe_chunks(chunks: list[Chunk]) -> list[Chunk]:
    """Drop duplicate identical embedding text (RT-05)."""
    seen: set[str] = set()
    unique: list[Chunk] = []
    for chunk in chunks:
        key = hashlib.sha256(chunk.text.strip().encode("utf-8")).hexdigest()
        if key in seen:
            logger.debug("Skipping duplicate chunk: %s", chunk.chunk_id)
            continue
        seen.add(key)
        unique.append(chunk)
    return unique
