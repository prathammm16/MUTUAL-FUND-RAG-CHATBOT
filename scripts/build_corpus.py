#!/usr/bin/env python3
"""
Phase 1.4–1.7 — build ``data/corpus/`` and ``data/chunks/`` from uploads/ or data/raw/.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ingestion.corpus import DEFAULT_CORPUS_DIR, build_corpus_from_imports  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build parsed corpus JSON (Phase 1.4)")
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--uploads-dir", type=Path, default=None)
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    built = build_corpus_from_imports(
        uploads_dir=args.uploads_dir,
        raw_dir=args.raw_dir,
        corpus_dir=args.corpus_dir,
    )
    if not built:
        logging.error("No schemes parsed. Add *.md files to uploads/ or data/raw/")
        return 1

    for scheme_id in sorted(built):
        logging.info("Wrote corpus %s (json, md, html)", scheme_id)
    logging.info("Built %d corpus + chunk sets in %s", len(built), args.corpus_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
