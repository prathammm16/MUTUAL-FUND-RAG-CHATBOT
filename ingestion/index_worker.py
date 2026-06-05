"""
Subprocess entrypoint to build a Chroma index and exit (releases file locks on Windows).

Called from ``run_daily.py`` before atomic directory swap.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ingestion.chunk_store import MIN_TOTAL_CHUNKS
from ingestion.index import index_corpus, validate_indexed_store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Chroma index in an isolated directory")
    parser.add_argument("staging_dir", type=Path)
    parser.add_argument("--ingested-at", default="")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    try:
        staging = str(args.staging_dir.resolve())
        total = index_corpus(
            persist_directory=staging,
            reset_collection=True,
            ingested_at=args.ingested_at or None,
        )
        if total < MIN_TOTAL_CHUNKS:
            raise RuntimeError(f"indexed only {total} chunks")
        errors = validate_indexed_store(staging)
        if errors:
            raise RuntimeError("; ".join(errors))
        print(f"indexed={total}")
        return 0
    except Exception as exc:
        logging.error("Index worker failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
