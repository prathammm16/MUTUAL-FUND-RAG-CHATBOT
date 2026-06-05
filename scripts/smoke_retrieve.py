#!/usr/bin/env python3
"""Phase 2.3 — smoke retrieval against Chroma (golden queries)."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.config import EMBEDDING_PROVIDER_LOCAL, get_settings  # noqa: E402
from ingestion.index import (  # noqa: E402
    collection_exists,
    query_chunks,
    validate_indexed_store,
)

# (query, expected scheme_id, expected sections)
SMOKE_CASES: list[tuple[str, str, frozenset[str]]] = [
    (
        "What is the expense ratio for HDFC Mid Cap Fund?",
        "hdfc-mid-cap",
        frozenset({"costs"}),
    ),
    (
        "What is the exit load on HDFC Gold ETF Fund of Fund?",
        "hdfc-gold-etf-fof",
        frozenset({"exit_load"}),
    ),
    (
        "Who manages the HDFC NIFTY 50 Index Fund?",
        "hdfc-nifty-50-index",
        frozenset({"fund_management"}),
    ),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke test vector retrieval (Phase 2)")
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=None,
        help="Override similarity threshold (default: 0.5 for local BGE, else settings)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    if not collection_exists():
        logging.error("No index found. Run: python scripts/build_index.py --reset")
        return 1

    store_errors = validate_indexed_store()
    if store_errors:
        for err in store_errors:
            logging.error("Index validation: %s", err)
        return 1

    settings = get_settings()
    min_sim = args.min_similarity
    if min_sim is None:
        min_sim = 0.5 if settings.embedding_provider == EMBEDDING_PROVIDER_LOCAL else settings.similarity_threshold

    failed = 0
    for query, expected_scheme, expected_sections in SMOKE_CASES:
        hits = query_chunks(query, min_similarity=min_sim)
        if not hits:
            logging.error("FAIL no hits: %s", query)
            failed += 1
            continue

        top = hits[0]
        ok_scheme = top.scheme_id == expected_scheme
        ok_section = top.section in expected_sections
        if ok_scheme and ok_section:
            logging.info(
                "OK %s -> %s / %s (sim=%.3f)",
                query[:50],
                top.scheme_id,
                top.section,
                top.similarity,
            )
        else:
            logging.error(
                "FAIL %s -> got %s / %s (expected %s / %s) sim=%.3f",
                query[:50],
                top.scheme_id,
                top.section,
                expected_scheme,
                ",".join(sorted(expected_sections)),
                top.similarity,
            )
            failed += 1

    if failed:
        logging.error("Smoke retrieval failed (%d/%d)", failed, len(SMOKE_CASES))
        return 1

    logging.info("Smoke retrieval PASSED (%d queries)", len(SMOKE_CASES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
