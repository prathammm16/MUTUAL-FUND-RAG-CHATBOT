"""
Retriever and context assembly (Phase 4).

Embeds factual queries, resolves scheme aliases, applies section-aware search,
provider-calibrated similarity thresholds, and builds the LLM ``[CONTEXT]`` block.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from app.config import (
    EMBEDDING_PROVIDER_LOCAL,
    get_all_schemes,
    get_settings,
    normalize_text,
    resolve_scheme_id_from_text,
)
from ingestion.index import (
    RetrievedChunk,
    collection_exists,
    query_chunks,
    resolve_index_dir,
)

NOT_FOUND_MESSAGE: Final[str] = (
    "I could not find that information in the HDFC Groww corpus for the five "
    "supported schemes. Try naming the fund (e.g. Mid Cap, Gold FoF, NIFTY 50) "
    "or ask about expense ratio, exit load, tax, minimum SIP, risk, benchmark, "
    "or fund managers."
)

_CONTEXT_HEADER: Final[str] = "[CONTEXT]"
_CONTEXT_FOOTER: Final[str] = "[/CONTEXT]"

# Section keyword hints (longest / specific phrases first within each section)
_SECTION_HINT_RULES: Final[tuple[tuple[str, frozenset[str]], ...]] = (
    (
        "fund_management",
        frozenset(
            {
                "fund manager",
                "who manages",
                "who is the manager",
                "managing since",
                "manager tenure",
                "manager education",
                "manager experience",
                "also manages",
            }
        ),
    ),
    (
        "costs",
        frozenset(
            {
                "expense ratio",
                "ter",
                "total expense",
                "fund expenses",
            }
        ),
    ),
    ("exit_load", frozenset({"exit load", "redemption charge", "redemption fee"})),
    (
        "minimum_investment",
        frozenset(
            {
                "minimum sip",
                "min sip",
                "minimum lumpsum",
                "min lumpsum",
                "minimum investment",
                "min investment",
            }
        ),
    ),
    (
        "tax",
        frozenset(
            {
                "taxation",
                "capital gains",
                "stcg",
                "ltcg",
                "tax on",
                "tax and",
            }
        ),
    ),
    ("benchmark", frozenset({"benchmark"})),
    ("risk", frozenset({"riskometer", "risk level", "risk grade"})),
)

_ALL_SCHEMES_PHRASES: Final[tuple[str, ...]] = (
    "all five",
    "all 5",
    "five schemes",
    "five funds",
    "every scheme",
    "each scheme",
    "all schemes",
    "all funds",
)

_MANAGER_STANDALONE_RE = re.compile(
    r"\b(?:manager|managers|fund manager)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RetrievalResult:
    """Outcome of a factual retrieval pass."""

    found: bool
    chunks: tuple[RetrievedChunk, ...]
    context: str
    scheme_id: str | None
    message: str
    citation_url: str | None
    last_updated: str | None


def effective_min_similarity(
    *,
    scheme_id: str | None,
    override: float | None = None,
) -> float:
    """
    Provider-aware similarity floor (BGE scores run lower than OpenAI).

    Local BGE: 0.60 with scheme filter, 0.55 without (empirical on 45-chunk index).
    OpenAI: ``SIMILARITY_THRESHOLD`` from settings (default 0.7).
    """
    if override is not None:
        return override
    settings = get_settings()
    if settings.embedding_provider == EMBEDDING_PROVIDER_LOCAL:
        return 0.60 if scheme_id else 0.55
    return settings.similarity_threshold


def infer_section_hint(query: str) -> str | None:
    """Map query keywords to a canonical corpus section (RT-03)."""
    normalized = normalize_text(query)
    for section, phrases in _SECTION_HINT_RULES:
        for phrase in phrases:
            if phrase in normalized:
                return section
    if _MANAGER_STANDALONE_RE.search(query):
        return "fund_management"
    return None


def query_implies_all_schemes(query: str) -> bool:
    """True when user asks across the full curated corpus (SC-07)."""
    normalized = normalize_text(query)
    return any(phrase in normalized for phrase in _ALL_SCHEMES_PHRASES)


def document_to_content(hit: RetrievedChunk) -> str:
    """Strip the embedding prefix from a stored document for LLM context."""
    marker = f" | Section: {hit.section} | "
    idx = hit.document.find(marker)
    if idx >= 0:
        return hit.document[idx + len(marker) :].strip()
    prefix = f"Scheme: {hit.scheme_name} | Section: {hit.section} | "
    if hit.document.startswith(prefix):
        return hit.document[len(prefix) :].strip()
    return hit.document.strip()


def build_context(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved chunks for the generator (task 4.4)."""
    if not chunks:
        return f"{_CONTEXT_HEADER}\n(no matching chunks)\n{_CONTEXT_FOOTER}"

    parts: list[str] = [_CONTEXT_HEADER]
    for i, hit in enumerate(chunks, start=1):
        content = document_to_content(hit)
        parts.append(
            f"--- Chunk {i} ---\n"
            f"scheme: {hit.scheme_name}\n"
            f"section: {hit.section}\n"
            f"source_url: {hit.source_url}\n"
            f"last_updated: {hit.last_updated or 'unknown'}\n"
            f"content:\n{content}"
        )
    parts.append(_CONTEXT_FOOTER)
    return "\n".join(parts)


def _merge_hits(primary: list[RetrievedChunk], fallback: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Prefer primary ordering; append fallback chunks not already present."""
    seen = {h.chunk_id for h in primary}
    merged = list(primary)
    for hit in fallback:
        if hit.chunk_id not in seen:
            merged.append(hit)
            seen.add(hit.chunk_id)
    return merged


def _retrieve_all_schemes(
    query: str,
    *,
    persist_directory: str | None,
    min_similarity: float,
    top_k_per_scheme: int = 1,
) -> list[RetrievedChunk]:
    """One top hit per curated scheme (SC-07)."""
    hits: list[RetrievedChunk] = []
    for scheme in get_all_schemes():
        scheme_hits = query_chunks(
            query,
            scheme_id=scheme.scheme_id,
            n_results=top_k_per_scheme,
            min_similarity=min_similarity,
            persist_directory=persist_directory,
        )
        if scheme_hits:
            hits.append(scheme_hits[0])
    hits.sort(key=lambda h: h.similarity, reverse=True)
    return hits


def retrieve(
    query: str,
    *,
    persist_directory: str | None = None,
    min_similarity: float | None = None,
    top_k: int | None = None,
) -> RetrievalResult:
    """
    Run the Phase 4 retrieval pipeline for a factual user query.

    Raises ``FileNotFoundError`` when the Chroma collection is missing (RT-02).
    """
    store = persist_directory
    if store is None:
        store = str(resolve_index_dir())

    if not collection_exists(store):
        raise FileNotFoundError(
            f"Vector index not found under {store}. Run: python scripts/build_index.py --reset"
        )

    settings = get_settings()
    k = top_k or settings.top_k
    scheme_id = resolve_scheme_id_from_text(query)
    section_hint = infer_section_hint(query)

    if query_implies_all_schemes(query):
        threshold = effective_min_similarity(scheme_id=None, override=min_similarity)
        hits = _retrieve_all_schemes(query, persist_directory=store, min_similarity=threshold)
        found = bool(hits)
        return RetrievalResult(
            found=found,
            chunks=tuple(hits),
            context=build_context(hits),
            scheme_id=None,
            message="" if found else NOT_FOUND_MESSAGE,
            citation_url=hits[0].source_url if hits else None,
            last_updated=hits[0].last_updated if hits else None,
        )

    threshold = effective_min_similarity(scheme_id=scheme_id, override=min_similarity)
    hits: list[RetrievedChunk] = []

    if section_hint == "fund_management" and scheme_id:
        hits = query_chunks(
            query,
            scheme_id=scheme_id,
            section="fund_management",
            n_results=min(k, 2),
            min_similarity=threshold,
            persist_directory=store,
        )

    if not hits:
        hits = query_chunks(
            query,
            scheme_id=scheme_id,
            n_results=k,
            min_similarity=threshold,
            persist_directory=store,
        )

    if section_hint and hits and hits[0].section != section_hint:
        boosted = query_chunks(
            query,
            scheme_id=scheme_id,
            section=section_hint,
            n_results=k,
            min_similarity=threshold,
            persist_directory=store,
        )
        if boosted:
            hits = _merge_hits(boosted, hits)[:k]

    found = bool(hits)
    return RetrievalResult(
        found=found,
        chunks=tuple(hits),
        context=build_context(hits),
        scheme_id=scheme_id,
        message="" if found else NOT_FOUND_MESSAGE,
        citation_url=hits[0].source_url if hits else None,
        last_updated=hits[0].last_updated if hits else None,
    )
