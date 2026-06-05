#!/usr/bin/env python3
"""
Phase 1 — validate parsed corpus, chunks, and log counts per scheme.

Usage:
    python scripts/validate_parse.py              # validate corpus + chunks
    python scripts/validate_parse.py --build      # parse, corpus, chunks, then validate
    python scripts/validate_parse.py --allow-partial  # do not require all 5 schemes
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running as ``python scripts/validate_parse.py`` from repo root.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ingestion.corpus import (  # noqa: E402
    DEFAULT_CORPUS_DIR,
    build_corpus_from_imports,
    load_corpus,
)
from ingestion.chunk_store import (  # noqa: E402
    DEFAULT_CHUNKS_DIR,
    load_all_chunks,
    validate_chunks_store,
)
from ingestion.validate import (  # noqa: E402
    log_chunk_counts,
    log_validation_report,
    validate_corpus,
)


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(message)s",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate corpus + chunks (Phase 1)")
    parser.add_argument(
        "--build",
        action="store_true",
        help="Parse uploads/ and data/raw/, write data/corpus/*.json, then validate",
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=DEFAULT_CORPUS_DIR,
        help=f"Corpus directory (default: {DEFAULT_CORPUS_DIR})",
    )
    parser.add_argument(
        "--uploads-dir",
        type=Path,
        default=None,
        help="Override uploads directory",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=None,
        help="Override data/raw directory",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Do not fail when fewer than 5 schemes are present",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    _configure_logging(args.verbose)

    if args.build:
        built = build_corpus_from_imports(
            uploads_dir=args.uploads_dir,
            raw_dir=args.raw_dir,
            corpus_dir=args.corpus_dir,
        )
        if not built:
            logging.error("No import files parsed; add markdown to uploads/ or data/raw/")
            return 1
        logging.info("Built %d corpus file(s) in %s", len(built), args.corpus_dir)

    corpus = load_corpus(args.corpus_dir)
    if not corpus:
        logging.error("No corpus JSON in %s (run with --build after adding imports)", args.corpus_dir)
        return 1

    report = validate_corpus(
        corpus,
        require_all_schemes=not args.allow_partial,
    )
    log_validation_report(report)
    if not report.ok:
        return 1

    chunk_errors = validate_chunks_store(
        DEFAULT_CHUNKS_DIR,
        require_all_schemes=not args.allow_partial,
    )
    chunks = load_all_chunks(DEFAULT_CHUNKS_DIR)
    log_chunk_counts(chunks)
    if chunk_errors:
        logging.error("Chunk validation FAILED")
        for err in chunk_errors:
            logging.error("  %s", err)
        return 1
    logging.info("Chunk validation PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
