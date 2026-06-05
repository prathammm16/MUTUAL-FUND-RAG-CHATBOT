#!/usr/bin/env python3
"""Phase 1.7 — build ``data/chunks/`` from ``data/corpus/*.json``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ingestion.chunk_store import (  # noqa: E402
    DEFAULT_CHUNKS_DIR,
    build_chunks_from_corpus_dir,
)
from ingestion.corpus import DEFAULT_CORPUS_DIR  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build chunk store (Phase 1.7)")
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--chunks-dir", type=Path, default=DEFAULT_CHUNKS_DIR)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    try:
        chunks = build_chunks_from_corpus_dir(
            corpus_dir=args.corpus_dir,
            chunks_dir=args.chunks_dir,
        )
        logging.info("Built %d chunks in %s", len(chunks), args.chunks_dir)
        return 0
    except Exception as exc:
        logging.error("Chunk build failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
