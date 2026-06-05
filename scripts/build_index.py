#!/usr/bin/env python3
"""Phase 2.2 — build Chroma index from ``data/chunks/``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ingestion.index import COLLECTION_NAME, index_corpus  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Chroma vector index (Phase 2)")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete and recreate the collection before indexing",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    try:
        total = index_corpus(reset_collection=args.reset)
        logging.info("Indexed %d chunks into %s", total, COLLECTION_NAME)
        return 0
    except Exception as exc:
        logging.error("Index build failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
